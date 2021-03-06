import requests
import json
import logging
from datetime import datetime
from selenium import webdriver
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
import subprocess
from modulepackermaster import launcher

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

    # adventure_list = [adventure_list[38]]

    # Grabbing my favorites
    adventure_list = [adventure_list[0], adventure_list[5], adventure_list[11], adventure_list[16], adventure_list[18],
                      adventure_list[20], adventure_list[38]]
    source_list = [source_list[0], source_list[1], source_list[2], source_list[7], source_list[8], source_list[14],
                   source_list[15], source_list[16], source_list[18]]

    # Start working on converting each item
    logger.info('starting adventures')
    for adventure in adventure_list:
        # adventure = adventure_list[1]

        adventure['module_root'] = create_filesys(adventure)
        fill_book_contents(adventure)
        # fill_book_md(adventure)
        fill_module_yaml(adventure)
        try:
            copy_images(adventure)
        except FileNotFoundError:
            logger.info(f'No images found for {adventure.get("name")}')
        # generate_module(adventure)

    logger.info('starting sources')
    for source in source_list:
        if source['id'] == 'rmr':
            logger.info('skipping rmr')
            continue
        else:
            source['module_root'] = create_filesys(source)
            fill_book_contents(source)
            # fill_book_md(source)
            fill_module_yaml(source)
            try:
                copy_images(source)
            except FileNotFoundError:
                logger.info(f'No images found for {source.get("name")}')
            # generate_module(source)



def create_filesys(module):
    """

    :param module:
    :return: (Path to module, 0 = already exists/1 = created)
    """
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
            elif module['type'] == 'book':
                os.mkdir(f'{path}\\img\\book')
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
    print(f'working on {module.get("id")}')
    json_contents = json.loads(module['json_fp'].read_bytes().decode())

    # # ! Turn on headless once finished
    # headless = 1
    #
    # if headless:
    #     chrome_options.add_argument("--headless")
    #
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
            section['section_root'] = str(Path(Path.cwd(), 'output', slugify(module.get("id"))))

            # Previously was storing each section in it's own file. Above removed that and sets section root as module root
            # section['section_root'] = f'{module.get("module_root")}\\{section.get("name").replace(":", "").replace(".", "")}'

            # dump the section json into a text doc in /data and create a section filesystem for the output
            try:
                # Removed section folders, everything going into module root
                os.mkdir(section['section_root'])
                # os.mkdir(f'{section["section_root"]}\\img')
                # if module['type'] == 'adventure':
                #     os.mkdir(f'{section["section_root"]}\\img\\adventure')
                # os.mkdir(f'{section["section_root"]}\\Encounters')
                # os.mkdir(f'{section["section_root"]}\\Maps')
                # open(Path(section['section_root'], "img", '.ignoregroup'), "a").close()
                pass
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
                            f"module-pagebreaks: h1, h2, h3\n" \
                            f"footer: My Custom Footer Texts\n" \
                            f"hide-footer: false\n" \
                            f"hide-footer-text: true\n" \
                            f"include-in: all\n" \
                            f"print-cover-only: false\n" \
                            f"---\n"
            # f"parent: {slugify(module.get('id'))}-{slugify(section.get('name'))}-contents\n" \

            text_to_write = fix_images(converted_json.text)

            with open(f'{section["section_root"]}\\{slugify(section.get("name"))}.md', "w+",
                      encoding="utf-8") as writer:
                writer.write(page_template)
                writer.write(text_to_write)
                logger.info(f'{section.get("name")}: md been written')

            # Disabled section files, don't need group yamls
            # fill_group_yaml(module, section)


# def fill_group_yaml(module, section):
#     '''
#     Not using this
#
#     :param module:
#     :param section:
#     :return:
#     '''
#     page_template = \
#         f"name: {section.get('name').replace(':', ' -')}\n" \
#         f"slug: {slugify(module.get('id'))}-{slugify(section.get('name'))}-contents\n" \
#         f"order: {section.get('index')+1}\n" \
#         f"module-pagebreaks: h1, h2\n" \
#         f"include-in: all\n" \
#         f"copy-files: true\n" \
#     # f"parent: {slugify(module.get('id'))}-main\n" \
#     # f"order: {index}\n" \
#
#     # ! Filepath with colon problem
#     with open(f'{module.get("module_root")}\\{section.get("name").replace(":", "").replace(".", "")}\\group.yaml', "w") as writer:
#         writer.write(page_template)


# def fill_book_md(module):
#     """
#     Isn't being used because I don't need it.
#     """
#
#     if os.path.exists(f'{module.get("module_root")}/module.yaml'):
#         return
#
#     page_template = \
#         f"---\n" \
#         f"name: {module.get('name')}\n" \
#         f"slug: {slugify(module.get('id'))}\n" \
#         f"module-pagebreak: h1, h2, h3\n" \
#         f"---\n"
#     # f"parent: {slugify(module.get('id'))}-main\n" \
#     # f"order: {options.get('order')}\n" \
#     # f"footer: My Custom Footer Texts\n" \
#     # f"hide-footer: false\n" \
#     # f"hide-footer-text: false\n" \
#     # f"include-in: all\n" \
#     # f"print-cover-only: false\n" \
#
#     with open(f'{module.get("module_root")}/{slugify(module.get("name"))}.md', "w") as writer:
#         writer.write(page_template)


def fill_module_yaml(module):
    try:
        level_start = module["level"]["start"]
        level_end = module["level"]["end"]
    except KeyError:
        level_start, level_end = ('custom', 'custom')

    if module['type'] == 'adventure':
        type = 'adventure'
    else:
        type = 'other'

    # TODO: Need to fix cover for tales
    # correct > cover: img/TftYP.png
    page_template = \
        f'---\n' \
        f'id: {uuid.uuid4()}\n' \
        f'name: {module.get("name").replace(":", " -")}\n' \
        f'slug: {slugify(module.get("id"))}-main\n' \
        f'description: Storyline - {module.get("storyline")}, Levels - {level_start}-{level_end}, Published - {module.get("published")}\n' \
        f'category: {type}\n' \
        f'author: WoTC\n' \
        f'cover: img/{module.get("id")}.png\n' \
        f'version: 1\n' \
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
    # TODO: The covers for Tales from the Yawning Portal have a different naming convention
    # cover: img\TftYP - TSC.png    < Bad
    # cover: img\TftYP.png          < Good

    try:
        if module['coverUrl'][:16] == 'img/covers/TftYP':
            module["coverUrl"] = Path(img_fp, 'covers', 'TftYP.png')
        else:
            module["coverUrl"] = Path(img_fp, 'covers', f'{module["id"]}.png')
        shutil.copy(module["coverUrl"], f'{module["module_root"]}\\img')
        # src = f'{module["module_root"]}\\img\\{module["id"]}.png'
        # dst = f'{module["module_root"]}\\img\\{module["id"]}.jpg'
        # os.rename(src, dst)
    except FileNotFoundError:
        module["coverUrl"] = Path(img_fp, 'covers', 'blank.png')
        shutil.copy(module["coverUrl"], f'{module["module_root"]}\\img')

    try:
        source = f'{img_fp}\\{module.get("type")}\\{module["id"]}'
        dest = f'{module["module_root"]}\\img\\{module.get("type")}\\{module["id"]}'
        shutil.copytree(source, dest)
    except FileNotFoundError:
        source = f'{img_fp}\\{module.get("type")}\\{module["id"][0:module["id"].find("-")]}'
        dest = f'{module["module_root"]}\\img\\{module.get("type")}\\{module["id"][0:module["id"].find("-")]}'
        shutil.copytree(source, dest)

    for index, filename in enumerate(os.listdir(dest)):
        src = Path(dest, filename)
        dst = Path(dest, filename.replace(' ', '-'))
        os.rename(src, dst)

    create_image_page(module)


def fix_images(text) -> str:
    # grabs the images file names and locations and calls grab_images() to move them to the directory
    pattern = '\[(img.*?)\?v.*?\](?=\n|$|\[|\()'
    r = re.compile(pattern)

    # makes the replacement in the text contents
    pattern = '\[(img\/.*?)\?v.*?](?:\n|$|(\(.*?(?:(?=\[)|\n|$|\)(?=\w))))'
    r = re.compile(pattern)
    matches = r.findall(text)

    # TODO: grab it first, replace it and grab it again

    text = r.sub(fr'\n![\2](\1)\n', text)
    # try:
    #     value = m_iter.__next__()
    #     text = r.sub(fr'![\3](../{value.group(1)}{value.group(2).replace(" ", "-")})\n', text)
    # except StopIteration:
    #     pass

    #     match[1]                            match[0]
    # ![(The Sword Coast (Player))\n](img / adventure / LMoP / The Sword Coast (Player).jpg)   < Original

    for match in matches:
        text = text.replace(f'![{match[1]}]({match[0]})', f'![{match[1].replace("(", "").replace(")", "")}]({match[0].replace(" ", "-")})')

    # you've got matches
    # you could cycle thorugh matches
    # searching for the match string
    # find it and replace it with a modified string

    return text

    # x = str(map(lambda value: r.sub(fr'![\2]({value.group(1).replace(" ", "-")})', text), m_matches))


def create_image_page(module):
    images_fp = f'{module.get("module_root")}\\img\\{module.get("type")}\\{module.get("id")}'

    with open(f'{module.get("module_root")}/Images.md', 'w') as w:
        w.write(f'---\n'
                f'name: Images\n'
                f'slug: {slugify(module.get("id"))}-images\n'
                f'order: 100\n'
                f"module-pagebreaks: h1, h2\n" \
                f'include-in: all\n'
                f'copy-files: true\n'
                f'---\n\n'
                f'# Cover, Maps and Images\n'
                f'![](img/{module.get("id")}.png)\n'
                )
        for index, filename in enumerate(os.listdir(images_fp)):
            w.write(f'## {filename}\n')
            w.write(f'![](img/{module.get("type")}/{module.get("id")}/{filename})\n\n')


def generate_module(module):
    # args = ['python', 'launcher.py', '--path', '"..\\output\\{module.get("id")}"', 'run']
    # p = subprocess.Popen(args, cwd=Path(Path.cwd(), 'modulepackermaster'), shell=True)
    # p.wait()

    path = f'output\\{module.get("id")}'
    output = module.get('id')

    launcher.removeIfExists('modulepackermaster/package.json')
    launcher.removeIfExists('modulepackermaster/package-lock.json')
    launcher.removeDirIfExists('modulepackermaster/cli-out')
    launcher.processTarget('makeFolders')
    launcher.copy('modulepackermaster/cli/package.cli.json', 'modulepackermaster/package.json')
    # launcher.run('npm.cmd install')
    p = subprocess.Popen(['npm', 'install'], cwd=Path(Path.cwd(), 'modulepackermaster'), shell=True)
    p = subprocess.Popen(['npm run compile-css'], cwd=Path(Path.cwd(), 'modulepackermaster'), shell=True)
    p = subprocess.Popen(['npm run compile-cli'], cwd=Path(Path.cwd(), 'modulepackermaster'), shell=True)
    launcher.run(f'node modulepackermaster/cli-out/cli/main.js "{path}" ""')


    # moduleproject.module
    src = Path(Path.cwd(), 'output', module['id'], 'moduleproject.module')
    dst = Path(Path.cwd(), 'output', module['id'], f'{module.get("id")}.module')
    os.rename(src, dst)


def fix_links():
    """
    {@creature Carrionette|VRGR}
    {@creature Gibbering mouther}
    {@book chapter 5|VRGR|5|Priests of Osybus}
    {@book Keepers of the Feather|VRGR|3|Keepers of the Feather}
    {@book Monster Manual|MM}
    {@book MM|MM}
    {@book chapter 5|VRGR|5}
    {@adventure Curse of Strahd|CoS}
    {@creature Vine Blight||vine blights}
    {@i Domain of Alien Memories} # itallics
    {@spell modify memory}
    {@b star spawn emissary} # bolded
    {@spell greater restoration}
    {@condition poisoned}
    {@skill Investigation}
    {@dice 1d6}

    :return:
    """
    pass


if __name__ == "__main__":
    main()
    print('complete')
