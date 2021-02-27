import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pdr", # Replace with your own username
    version="0.4.2a",
    author="Chase Million",
    author_email="chase@millionconcepts.com",
    description="Planetary Data Reader",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MillionConcepts/pdr",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        "pds4_tools",
        "rasterio",
        "pandas",
        "numpy",
        "astropy",
        "pvl>=1.1.0",
        "python-Levenshtein",
        "scikit-image",
    ]

)
