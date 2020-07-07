import setuptools

from os import path
from fnmatch import fnmatch
import os


def package_data_with_recursive_dirs(package_data_spec):
    """converts modified package_data dict to a classic package_data dict
    Where normal package_data entries can only specify globs, the
    modified package_data dict can have
       a) directory names or
       b) tuples of a directory name and a pattern
    as entries in addition to normal globs.
    When one of a) or b) is encountered, the entry is expanded so
    that the resulting package_data contains all files (optionally
    filtered by pattern) encountered by recursively searching the
    directory.
    
    Usage:
    setup(
    ...
        package_data = package_data_with_recursive_dirs({
            'module': ['dir1', ('dir2', '*.xyz')],
            'module2': ['dir3/file1.txt']
                })
    )
    """
    out_spec = {}
    for package_name, spec in package_data_spec.items():
        # replace dots by operating system path separator
        package_path = path.join(*package_name.split('.'))
        out_entries = []
        for entry in spec:
            directory = None  # full path to data dir
            pattern = None  # pattern to append
            datadir = None  # data dir relative to package (as specified)
            try:  # entry is just a string
                directory = path.join(package_path, entry)
                datadir = entry
                pattern = None
            except (TypeError, AttributeError):  # entry has additional pattern spec
                directory = path.join(package_path, entry[0])
                pattern = entry[1]
                datadir = entry[0]
            if path.isdir(directory):  # only apply if it is really a directory
                for (dirpath, dirnames, filenames) in os.walk(directory):
                    for filename in (path.join(dirpath, f) for f in filenames):
                        if not pattern or fnmatch(filename, pattern):
                            relname = path.normpath(path.join(datadir, path.relpath(filename, directory)))
                            out_entries.append(relname)
            else:  # datadir is not really a datadir but a glob or something else
                out_entries.append(datadir)  # we just copy the entry
        out_spec[package_name] = out_entries
    return out_spec

with open("README.md", "r") as fd:
    long_description = fd.read()

setuptools.setup(
    name="wagtail_to_ion",
    version="1.1.4",
    author="anfema GmbH",
    author_email="admin@anfe.ma",
    description="Wagtail to ION API adapter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/anfema/wagtail_to_ion",
    packages=setuptools.find_packages(),
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3 :: Only",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django :: 2.2",
        "Framework :: Wagtail :: 2",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries",
    ],
    keywords="ION Wagtail API Adapter",
    install_requires=[
        "django>=2.2",
        "wagtail>2.0",
        "celery[redis]>=4.3",
        "djangorestframework>=3.9",
        "beautifulsoup4>=4.6",
        "wagtailmedia>=0.4",
        "python-magic>=0.4",
    ],
    python_requires='>=3.5',
    package_data=package_data_with_recursive_dirs({
        "wagtail_to_ion": [
            "templates",
            "static"
        ]
    })
)
