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
designed to planetary science data into standard python objects. `pdr` is
written accessibly to the introductory Python user. To read a data file one
must simply import `pdr` and call `pdr.read(fn)` where `fn` is the 
label or data file, and `pdr` will load all the products data and metadata.
Typically, `pdr` loads image data as `numpy` ndarrays while tabular data is
represented as `pandas` DataFrames.

`pdr` reads data products held by the Planetary Data System (PDS) that follow 
either PDS3 `@PDS3` or PDS4 `@PDS4` standards. However, rather than 
implementing the standards to the letter, we've followed a **data-driven 
development** approach. We created manifests of the holdings of each of 
the PDS nodes and reference them to select a sample subset of each type of 
data, make changes to `pdr`, if necessary, to support that data type, and then 
add it to a test corpus. That test corpus is then used to confirm any changes 
made do not `pdr` cause compatibility regressions with any other data types 
that were previously supported. The core of `pdr` is made of extremely flexible
heuristics that automatically detect the type of data passed, and correct for 
any deviations it may have from the standard, because it is assumed from the 
outset that many data products will not conform. Thus, it is compatible with 
the reality of how the data is formatted and labeled. Our methods for adding 
dataset support are further described in `@Kaufman:2022` and the repository 
for the testing toolchain can be found in `@pdr-tests`. `pdr` also supports 
some common scientific interchange data formats that are not PDS labelled, 
including FITS.

# Statement of need
A major pain point for planetary scientists is simply figuring out how to
access their data. In particular, data archived under the PDS3 standards can be
especially challenging due to inconsistent or specialized formatting. While the
newer PDS4 standards are significantly stricter, much of the holdings of PDS
have not yet been migrated to this standard.

`pdr` is currently in use on the Perseverance rover mission.
It allows for extremely fast metadata parsing without loading an
entire file making it well suited to working with large data files on a 
tactical timeline.

# Acknowledgements
The development of pdr is supported by NASA grant No. 80NSSC21K0885. 
We would like to thank the Planetary Data System (PDS) for their continued 
cooperation with this project.

# References