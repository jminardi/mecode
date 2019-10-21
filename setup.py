from setuptools import setup, find_packages

INFO = {'name': 'mecode',
        'version': '0.3.0',
        'description': 'Simple GCode generator',
        'author': 'Jack Minardi',
        'author_email': 'jack@minardi.org',
        }

setup(
    name=INFO['name'],
    version=INFO['version'],
    description=INFO['description'],
    author=INFO['author'],
    author_email=INFO['author_email'],
    packages=find_packages(),
    url='https://github.com/jminardi/mecode',
    download_url='https://github.com/jminardi/mecode/tarball/master',
    keywords=['gcode', '3dprinting', 'cnc', 'reprap', 'additive'],
    zip_safe=False,
    package_data = {
        '': ['*.txt', '*.md'],
    },
    install_requires=[
        'pyserial',
        'numpy',
    ],
)
