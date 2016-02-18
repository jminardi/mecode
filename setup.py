from setuptools import setup, find_packages

INFO = {'name': 'mecode',
        'version': '0.2.2',
        'author': 'Jack Minardi',
        'author_email': 'jack@minardi.org',
        }

setup(
    name=INFO['name'],
    version=INFO['version'],
    author=INFO['author'],
    author_email=INFO['author_email'],
    packages=find_packages(),
    url='https://github.com/jminardi/mecode',
    download_url='https://github.com/jminardi/mecode/tarball/master',
    keywords=['gcode', '3dprinting', 'cnc', 'reprap'],
    zip_safe=False,
    data_files = [
        ("./mecode", [
            "mecode/header.txt",
            "mecode/footer.txt"])],
)
