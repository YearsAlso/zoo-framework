from distutils.core import setup
from setuptools import find_packages

with open("README.rst", "r") as f:
    long_description = f.read()

setup(name='zoo',  # 包名
      version='1.0.0',  # 版本号
      description='zoo framework',
      long_description=long_description,
      author='xmeng',
      author_email='xmeng931015@live.com',
      install_requires=[],
      license='Apache License',
      packages=find_packages(),
      platforms=["all"],
      classifiers=[
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Natural Language :: Chinese (Simplified)',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Topic :: Software Development :: Libraries'
      ],
      )
