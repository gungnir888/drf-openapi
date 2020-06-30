#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='drf_openapi3',
    description='Manage OpenApi documentation with DRF',
    version='0.1.0',
    author='Davide Pugliese',
    author_email='davide.pglse@gmail.com',
    license='GPL',
    url='https://github.com/gungnir888/drf-openapi',
    long_description=open('README.rst').read(),
    packages=find_packages(),
    include_package_data = True,
    python_requires='>3.6.0',
    install_requires=[
        'Django',
        'djangorestframework'
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: System :: Installation/Setup'
    ]
)
