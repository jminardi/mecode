from setuptools import setup, find_packages

INFO = {'name': 'mecode',
        'version': '0.1.0',
        }

setup(
    name=INFO['name'],
    version=INFO['version'],
    author='Jack Minardi',
    packages=find_packages(),
    zip_safe=False,
    maintainer='Jack Minardi',
    maintainer_email='jack@minardi.org',
)
