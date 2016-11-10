from setuptools import setup, find_packages
import sys

TEST_REQUIRES = ['pytest']
if sys.version_info[:2] < (3, 3):
    TEST_REQUIRES += ['mock']

INFO = {'name': 'mecode',
        'version': '0.2.7',
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
    keywords=['gcode', '3dprinting', 'cnc', 'reprap'],
    zip_safe=False,
    package_data = {
        '': ['*.txt', '*.md'],
    },
    setup_requires=['pytest-runner'],
    install_requires=[
        'pyserial',
        'numpy',
    ],
    tests_require=TEST_REQUIRES,
)
