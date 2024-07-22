---
title: 'PDR: The Planetary Data Reader'
tags:
  - Python
  - planetary science
authors:
  - name: Sierra Brown
    orcid: 0000-0001-6065-5461
    affiliation: 1
  - name: Michael St. Clair
    orcid: 0000-0002-7877-3148
    affiliation: 1
  - name: Chase Million
    orcid: 0000-0003-2732-3486
    affiliation: 1
  - name: Sabrina A. Curtis
    orcid: 0009-0004-6071-5865
    affiliation: 1
affiliations:
  - name: Million Concepts LLC
    index: 1
date: 16 July 2024
bibliography: paper.bib
---
# Summary

The Planetary Data Reader, `pdr`, is an open-source Python-language package
that reads data stored in planetary science formats and converts it into
standard Python objects. It typically loads images as `ndarrays`, tables
as Pandas `DataFrames`, and metadata and ancillary data as strings or dicts.
`pdr`'s interface is designed to be maximally accessible to the introductory
Python user. To read a data file, a user must simply `import pdr`, then run 
`pdr.read(fn)`, where `fn` is the product's label or data file. `pdr` will 
immediately load the product's metadata, then lazily load data objects when 
referenced.


`pdr` reads data products held by the Planetary Data System (PDS) that follow 
either PDS3 `[@PDS3]` or PDS4 `[@PDS4]` standards--meaning in practice that they
have metadata labels that generally follow one of these two formats. (It also
supports some common scientific interchange data formats that are not PDS, 
including FITS.) We knew from the outset that many products in the PDS were not
fully standards-compliant, particularly those archived under PDS3; its holdings
are extremely diverse and span over half a century. For this reason, 
we took a **data-driven development** approach rather than attempting to implement
these standards to the letter. What this means in practice is that we built `pdr` 
around a core of extremely flexible heuristics that permit it to permissively accept
and correctly handle many products that deviate from the standards.

We have developed these heuristics through an iterative design process centered on
examination of actually-existing data. We created manifests of the holdings of each 
of the PDS nodes, then used them to help identify 'types' of data and retrieve
representative samples of each 'type' (the PDS holds hundreds of millions of files
with a total data volume in the petabytes, so examining every file is impractical).

When we examine a new type, we verify the correctness of `pdr`'s behavior across
our sample of that type and make changes to `pdr` as necessary to support that 
type's characteristics. We then add one or two individual products of that type
to a data corpus we use for regression testing. This has permitted us to design
software that conforms to planetary data rather than planetary data standards.
Our methods for adding dataset support are further described in `@Kaufman:2022`,
and our testing toolchain can be found in`@pdr-tests`. 

`pdr` is an affliate package of `planetarypy` `[@planetarypy]`. It is available
on the Python Package Index and `conda-forge`.

# Statement of need

_Just accessing data_ is a major pain point for planetary scientists. Data 
archived under the PDS3 standards can be especially challenging due to inconsistent,
specialized, or flatly incorrect formatting. While the newer PDS4 standards are 
significantly stricter, many of the holdings of the PDS have not yet been migrated
to this standard. `pdr` can remove months of preparatory work, making it faster
for scientists to get to core research tasks and making it much more practical
for them to incorporate data sets they haven't worked with previously into their
research.

The simplicity and consistency of `pdr`'s API, along with its speed and stability,
make it ideal for use in automated data processing pipelines. `pdr` is currently 
used in a wide variety of planetary projects. These include the Perseverance Rover's 
MastCamZ tactical pipeline `@StClair:2023` and PDS3 to PDS4 migration pipelines for
data from Clementine `[@Clementine]`, Chandrayaan-1 M3 `[@M3]`, and the Viking Orbiter 
cameras `[@Viking]`. (Its fast metadata parsing features make it especially appealing
for converting metadata standards across tens of millions of products.)

# Other packages

There is a very wide variety of software intended to read data in planetary science 
formats. `pdr`'s most important distinctions are its emphasis on breadth, simplicity,
and high compatibility with other tools. `pdr` incorporates some of this software,
including `pds4_tools` `[@pds4_tools]` and `astropy.io.fits` `[@astropy]`. `pdr` uses
these packages to read, respectively, PDS4 and FITS files, converting their outputs
into standard Python objects to provide users with a common interface regardless
of file format. 

It is important to note that many pieces of software with narrower _format_ scope than
`pdr` have wider _application_ scope. For instance, GDAL `[@GDAL]` and `rasterio` 
`[@rasterio]` (which uses GDAL) read a narrower range of data and do not provide as 
consistent or straightforward an interface, but will deal with map projection 
transformations; VICAR `[@VICAR]` reads only VICAR-processed data, but is also a 
comprehensive image processing toolkit; `plio` `[@plio]` only reads data in a few formats,
but is capable of applying instrument-specific metadata-parsing rules. Many of these
tools also offer write capabilities, which `pdr` does not. Users who require write
capabilities or subdomain-specific behaviors might find narrowly-focused tools more 
appropriate; they might also find `pdr` useful as a preprocessor for such tools.

# Acknowledgements

The development of pdr is supported by NASA grant No. 80NSSC21K0885. We would like to 
thank the Planetary Data System (PDS) for their continued cooperation with this project.

# References
