import os
from setuptools import setup, find_packages


local_dir = os.path.dirname(os.path.realpath(__file__))


about = {}
with open(os.path.join(local_dir, 'pds4_tools', '__about__.py')) as f:
    exec(f.read(), about)


def read(filename, full_path=False):
    if not full_path: filename = os.path.join(local_dir, filename)
    with open(filename, 'r') as file_handler:
        data = file_handler.read()

    return data


def get_docs_url():

    base_url = 'https://pdssbn.astro.umd.edu/tools/pds4_tools_docs/'

    if 'dev' in about['__version__']:
        return base_url + 'current/'
    else:
        return base_url + about['__version__'] + '/'


setup(
    name='pds4_tools',
    version=about['__version__'],

    description='Package to read and display NASA PDS4 data',
    long_description=read('README.rst'),
    long_description_content_type='text/x-rst',

    author=about['__author__'],
    author_email=about['__email__'],

    url='https://sbnwiki.astro.umd.edu/wiki/Python_PDS4_Tools',
    license='BSD',
    keywords=['pds4_viewer', 'pds4', 'pds'],

    project_urls={
        'Documentation': get_docs_url(),
        'Source Code': 'https://github.com/Small-Bodies-Node/pds4_tools',
        'Bug Tracker': 'https://github.com/Small-Bodies-Node/pds4_tools/issues',
    },

    classifiers=[
        'Development Status :: 5 - Production/Stable',

        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Scientific/Engineering :: Physics',

        'License :: OSI Approved :: BSD License',

        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: Unix',
        'Operating System :: MacOS',

        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],

    packages=find_packages(exclude=['doc', '*.tests', '*.tests.*']),
    package_data={'': ['viewer/logo/*']},

    zip_safe=False,

    install_requires=[
        'numpy',
    ],

    extras_require={
        'viewer': ['matplotlib'],  # tkinter
        'tests': ['pytest'],
    }
)
