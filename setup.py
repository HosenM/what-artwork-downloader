'''
Created on 05.03.2015

'''

from setuptools import setup, find_packages

setup(
      name='what-artwork-downloader',
      version='0.1.1',
      description='What.cd Artwork Downloader',
      author='XHFHX',
      author_email='',
      url='https://github.com/capital-G/what-artwork-downloader',
      install_requires = [
                          "requests",
                          "whatapi",
                          "mutagen",
                          "Pillow"
                          ],
      packages=find_packages(exclude=('tests', 'docs')),
      package_data = {
                      '': ['*.txt']
                      },
      zip_safe=True
)