from setuptools import setup, find_packages

INFO = {'name': 'mecode',
        'version': '0.2.1',
        }

setup(
    data_files = [
        ("./mecode", [
            "mecode/header.txt",
            "mecode/footer.txt"])],
    name=INFO['name'],
    version=INFO['version'],
    author='Jack Minardi',
    packages=find_packages(),
    zip_safe=False,
    maintainer='Jack Minardi',
    maintainer_email='jack@minardi.org',
)
