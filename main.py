import requests
import json
import logging
from datetime import datetime
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
import os
from time import sleep
from slugify import slugify
import zipfile
import uuid
import shutil
import re

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=f'{Path.cwd()}/logs/{datetime.now().strftime("%Y%m%d-%H%M%S")}.log',
    level=logging.DEBUG)
PATH = "C:\\Program Files (x86)\\chromedriver_win32\\chromedriver.exe"

chrome_options = Options()
# chrome_options.add_argument("--headless")

renderer_url = 'https://noads.5e.tools/renderdemo.html'
data_fp = Path(Path.cwd(), 'sources/5eTools.1.129.0/data/')
img_fp = Path(Path.cwd(), 'sources/5eTools_img.1.129.0/tmp/5et/img')


def main():
    # download_5e()
    setup_modules()


def download_5e(img=0):
    logger.info('-- Beginning Download of 5e.Tools --')
    url = 'https://get.5e.tools/release/5eTools.1.129.0.zip'
    images = 'https://get.5e.tools/img/5eTools_img.1.129.0.zip'

    try:
        os.mkdir(Path(Path.cwd(), "sources"))
    except OSError:
        print('Error creating file structure.')

    dest = Path(Path.cwd(), 'sources')
    chunk_size = 128

    # downloads the most recent version of 5e.tools
    r = requests.get(url, stream=True)
    with open(Path(dest, '5eTools.1.129.0.zip'), 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            logger.info("downloading 5eTools...")
            fd.write(chunk)
        logger.info("download complete")

    with zipfile.ZipFile(Path(dest, '5eTools.1.129.0.zip'), 'r') as zip_ref:
        zip_ref.extractall(Path(dest, '5eTools.1.129.0'))
    logger.info("unzip complete")

    # optional download of the most recent version of 5e.tools's images
    if img:
        r = requests.get(images, stream=True)
        with open(Path(dest, '5eTools_img.1.129.0.zip'), 'wb') as fd:
            for chunk in r.iter_content(chunk_size=chunk_size):
                logger.info("downloading images...")
                fd.write(chunk)
        logger.info("download complete")

        with zipfile.ZipFile(Path(dest, '5eTools_img.1.129.0.zip'), 'r') as zip_ref:
            zip_ref.extractall(Path(dest, '5eTools_img.1.129.0'))
        logger.info("unzip complete")


def setup_modules():
    logger.info('setting up modules')
    adventure_list = json.loads(Path(data_fp, 'adventures.json').read_bytes().decode())['adventure']
    source_list = json.loads(Path(data_fp, 'books.json').read_bytes().decode())['book']

    # Add location of where their book is inside 5e.tools site data
    for adventure in adventure_list:
        adventure['type'] = 'adventure'
        adventure['json_fp'] = Path(data_fp, 'adventure', f'adventure-{slugify(adventure.get("id"))}.json')

    for source in source_list:
        source['type'] = 'book'
        source['json_fp'] = Path(data_fp, 'book', f'book-{slugify(source.get("id"))}.json')

    # Start working on converting each item
    for adventure in adventure_list:
        # adventure = adventure_list[1]
        logger.info('starting adventures')
        adventure['module_root'] = create_filesys(adventure)
        fill_book_contents(adventure)
        # fill_book_md(adventure)
        fill_module_yaml(adventure)
        try:
            copy_images(adventure)
        except FileNotFoundError:
            logger.info(f'No images found for {adventure.get("name")}')

    for source in source_list:
        if source['id'] == 'rmr':
            logger.info('skipping rmr')
            continue
        else:
            logger.info('starting sources')
            source['module_root'] = create_filesys(source)
            fill_book_contents(source)
            # fill_book_md(source)
            fill_module_yaml(source)
            copy_images(source)


def create_filesys(module) -> Path:
    path = Path(Path.cwd(), 'output', slugify(module.get("id")))
    try:
        os.mkdir(path)
        try:
            # os.mkdir(Path(path, "Encounters"))
            # os.mkdir(Path(path, "Maps"))
            # os.mkdir(Path(path, "Images"))
            os.mkdir(f'{path}\\img')
            open(Path(path, "img", '.ignoregroup'), "a").close()
            if module['type'] == 'adventure':
                os.mkdir(f'{path}\\img\\adventure')
            os.mkdir(Path(path, "data"))
            open(Path(path, "data", '.ignoregroup'), "a").close()
            # open(Path(path, f'{slugify(module.get("name"))}.md'), "a").close()
            open(Path(path, 'module.yaml'), "a").close()
        except OSError:
            logger.error('Error creating file structure.')
    except OSError:
        logger.error(f'{module.get("name")} already exists')
    logger.info(f'{module.get("name")}: filesystem created')

    return path


def fill_book_contents(module):
    json_contents = json.loads(module['json_fp'].read_bytes().decode())

    # # ! Turn on headless once finished
    # headless = 1
    #
    # if headless:
    #     chrome_options.add_argument("--headless")

    with webdriver.Chrome(PATH, options=chrome_options) as wd:
        wait = WebDriverWait(wd, 5)

        try:
            wd.get(renderer_url)
            pass
        except TimeoutError:
            raise TimeoutError('Timed out loading renderer')

        wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'ace_content')))
        window = wd.find_element_by_class_name('ace_text-input')
        render_type = Select(wd.find_element_by_id('demoSelectRenderer'))
        render_type.select_by_value('md')

        data_path = Path(module.get('module_root'), 'data')

        try:
            # os.mkdir(Path(module.get('module_root'), module.get("name").replace(':', ' -')))
            os.mkdir(data_path)
        except OSError:
            logger.error(f'{module.get("name")}: Could not make module folder')

        for index, section in enumerate(json_contents['data']):
            section['index'] = index

            # ! Filepath with colon problem
            section['section_root'] = f'{module.get("module_root")}\\{section.get("name").replace(":", "").replace(".", "")}'

            # dump the section json into a text doc in /data and create a section filesystem for the output
            try:
                os.mkdir(section['section_root'])
                # os.mkdir(f'{section["section_root"]}\\img')
                # if module['type'] == 'adventure':
                #     os.mkdir(f'{section["section_root"]}\\img\\adventure')
                os.mkdir(f'{section["section_root"]}\\Encounters')
                # os.mkdir(f'{section["section_root"]}\\Maps')
                # open(Path(section['section_root'], "img", '.ignoregroup'), "a").close()
            except OSError:
                logger.error('Error creating file structure.')

            with open(f'{data_path}\\{section.get("id")}.txt', "w") as writer:
                writer.write(json.dumps(section, indent=4))

            # grab the text and paste it into the active window
            command = f'clip < {data_path}\{section.get("id")}.txt'
            os.system(command)
            sleep(.5)
            window.send_keys(Keys.CONTROL, "a")
            window.send_keys(Keys.DELETE)
            window.send_keys(Keys.CONTROL, "v")
            sleep(1)

            # TODO: Don't be lazy and actually check if the rendered text is there.
            # wait.until(EC.text_to_be_present_in_element(wd.find_element_by_id('pagecontent'), section['name']))

            # grab the converted text element and save it as a .md
            converted_json = wd.find_element_by_id('pagecontent')
            page_template = f"---\n" \
                            f'name: {section.get("name").replace(":", " -")}\n' \
                            f"slug: {slugify(module.get('id'))}-{slugify(section.get('name'))}-page\n" \
                            f"order: {section.get('index')}\n" \
                            f"footer: My Custom Footer Texts\n" \
                            f"hide-footer: false\n" \
                            f"hide-footer-text: true\n" \
                            f"include-in: all\n" \
                            f"print-cover-only: false\n" \
                            f"---\n"
    # f"parent: {slugify(module.get('id'))}-{slugify(section.get('name'))}-contents\n" \

            text_to_write = fix_images(converted_json.text)

            with open(f'{section["section_root"]}\\{slugify(section.get("name"))}.md', "w+", encoding="utf-8") as writer:
                writer.write(page_template)
                writer.write(text_to_write)
                logger.info(f'{section.get("name")}: md been written')

            fill_group_yaml(module, section)


def fill_group_yaml(module, section):
    page_template = \
        f"name: {section.get('name').replace(':', ' -')}\n" \
        f"slug: {slugify(module.get('id'))}-{slugify(section.get('name'))}-contents\n" \
        f"order: {section.get('index')+1}\n"\
        f"include-in: all\n" \
        f"copy-files: true\n" \
    # f"parent: {slugify(module.get('id'))}-main\n" \
    # f"order: {index}\n" \

    # ! Filepath with colon problem
    with open(f'{module.get("module_root")}\\{section.get("name").replace(":", "").replace(".", "")}\\group.yaml', "w") as writer:
        writer.write(page_template)


def fill_book_md(module):
    page_template = \
        f"---\n" \
        f"name: {module.get('name')}\n" \
        f"slug: {slugify(module.get('id'))}\n" \
        f"---\n"
    # f"parent: {slugify(module.get('id'))}-main\n" \
    # f"order: {options.get('order')}\n" \
    # f"footer: My Custom Footer Texts\n" \
    # f"hide-footer: false\n" \
    # f"hide-footer-text: false\n" \
    # f"include-in: all\n" \
    # f"print-cover-only: false\n" \

    with open(f'{module.get("module_root")}/{slugify(module.get("name"))}.md', "w") as writer:
        writer.write(page_template)


def fill_module_yaml(module):
    try:
        level_start = module["level"]["start"]
        level_end = module["level"]["end"]
    except KeyError:
        level_start, level_end = ('custom', 'custom')

    page_template = \
        f'id: {uuid.uuid4()}\n'\
        f'name: {module.get("name")}\n'\
        f'slug: {slugify(module.get("id"))}-main\n'\
        f'description: Storyline - {module.get("storyline")}, Levels - {level_start}-{level_end}, Published - {module.get("published")}\n'\
        f'category: {module.get("type")}\n'\
        f'author: WoTC\n'\
        f'cover: img\\{module.get("id")}.png\n'\
        f'version: 1\n'\
        f'autoIncrementVersion: true\n' \
    # f'print-cover: {module.get("coverURL")}\n'\
    # f'maps:
    # f'\tpath:
    # f'\torder:
    # f'\tparent:
    # f'\tslug:
    # f'encounters:
    # f'\tpath:
    # f'\torder:
    # f'\tparent:
    # f'\tslug:

    with open(f'{module.get("module_root")}/module.yaml', "w") as writer:
        writer.write(page_template)


def copy_images(module):
    try:
        module["coverURL"] = Path(img_fp, 'covers', f'{module["id"]}.png')
        shutil.copy(module["coverURL"], f'{module["module_root"]}\\img')
    except FileNotFoundError:
        module["coverURL"] = Path(img_fp, 'covers', f'{module["id"][0:module["id"].find("-")]}.png')
        shutil.copy(module["coverURL"], f'{module["module_root"]}\\img')

    if module['type'] == 'adventure':
        try:
            source = f'{img_fp}\\{"adventure"}\\{module["id"]}'
            dest = f'{module["module_root"]}\\img\\adventure\\{module["id"]}'
            shutil.copytree(source, dest)
        except FileNotFoundError:
            source = f'{img_fp}\\{"adventure"}\\{module["id"][0:module["id"].find("-")]}'
            dest = f'{module["module_root"]}\\img\\adventure\\{module["id"][0:module["id"].find("-")]}'
            shutil.copytree(source, dest)

        for index, filename in enumerate(os.listdir(dest)):
            src = Path(dest, filename)
            dst = Path(dest, filename.replace(' ', '-'))
            os.rename(src, dst)


def fix_images(text) -> str:
    # grabs the images file names and locations and calls grab_images() to move them to the directory
    pattern = '\[(img.*?)\?v.*?\](?=\n|$|\[|\()'
    r = re.compile(pattern)
    grab_images(re.findall(pattern, text))

    # makes the replacement in the text contents
    pattern = '\[(img\/adventure\/.*?\/)(.*?)\?v.*?](?:\n|$|(?:\((.*?)\)(?:(?=\[)|(?=\n)|(?=$))))'
    r = re.compile(pattern)
    matches = r.findall(text)

    # TODO: grab it first, replace it and grab it again

    text = r.sub(fr'\n![\3](../\1\2)\n', text)
    # try:
    #     value = m_iter.__next__()
    #     text = r.sub(fr'![\3](../{value.group(1)}{value.group(2).replace(" ", "-")})\n', text)
    # except StopIteration:
    #     pass

    for match in matches:
        text = text.replace(f'{match[0]}{match[1]}', f'{match[0]}{match[1].replace(" ", "-")}')


    #you've got matches
    #you could cycle thorugh matches
    #searching for the match string
    #find it and replace it with a modified string

    return text

    # x = str(map(lambda value: r.sub(fr'![\2]({value.group(1).replace(" ", "-")})', text), m_matches))

def grab_images(image_list):
    pass


if __name__ == "__main__":
    main()
    print('complete')
