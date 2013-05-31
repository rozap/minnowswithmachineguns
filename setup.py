#!/usr/bin/env python

from distutils.core import setup

setup(name='minnowswithmachineguns',
      version='0.0.2',
      description='A utility for arming (creating) many minnows (digital ocean instances) to attack (load test) targets (web applications). Based on beeswithmachineguns',
      author='Chris Duranti',
      author_email='chrisd1891@gmail.com',
      url='https://github.com/rozap/minnowswithmachineguns',
      license='MIT',
      packages=['minnowswithmachineguns'],
      scripts=['minnows'],
      install_requires=[
          'dop==0.1.4',
          'paramiko==1.10.1'
          ],
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Testing :: Traffic Generation',
          'Topic :: Utilities',
          ],
     )
