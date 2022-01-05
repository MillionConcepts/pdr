# Datasets Supported by PDR:

Datasets can be considered to be supported by PDR in one of two categories: officially supported, or notionally supported.

**_Officially supported datasets_** have been extensively tested and all data of this type is supported. 
If you encounter a file of this type that does not open with pdr, please open an issue at: https://github.com/MillionConcepts/pdr/issues

**_Notionally supported datasets_** have been manually tested with a small number of files and these were sucessfully opened by pdr.
Some of these do not conform to PDS standards (such as missing label files) and cannot be tested fully.
Others in this category will be moved to officially supported upon completion of the testing procedure.

## Officially Supported Datasets:

- LROC
  - WAC CDR
  - WAC EDR
  - NAC CDR
  - NAC EDR
  - NAC raw image data (NACR and NACL in image name): Note: We think thi sowrks, but couldn't validate the output because it would require recreating portions of the ground processing pipeline.
  - NAC DTM
  - WAC EMP
  - WAC HAPKE
  - WAC HAPKE PARAMMAP
  - WAC ORBITS
  - WAC POLE ILL
  - WAC TIO2

## Notionally Supported Datasets:

- LROC
  - Anaglyphs
  - NAC DTM without labels (housed under EXTRAS folder in LROC database)
  - WAC EMP tif files without labels (housed under EXTRAS folder in LROC database)
  - WAC HAPKE tif files without labels (housed under EXTRAS folder in LROC database)

