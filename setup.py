import setuptools

with open("README.md", "r") as fd:
    long_description = fd.read()

setuptools.setup(
    name="wagtail_to_ion",
    version="1.0.0",
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
)
