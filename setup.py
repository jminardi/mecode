from os import path
from setuptools import setup, find_packages

INFO = {'name': 'mecode',
        'version': '0.2.10',
        'description': 'Simple GCode generator',
        'author': 'Jack Minardi',
        'author_email': 'jack@minardi.org',
        }
here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'requirements.txt')) as requirements_file:
    # Parse requirements.txt, ignoring any commented-out lines.
    requirements = [line for line in requirements_file.read().splitlines()
                    if not line.startswith('#')]
    
requirements = [r for r in requirements if not r.startswith('git+')]

test_requirements = ['mock' ]

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
    install_requires=requirements,
    tests_require=test_requirements,
)
