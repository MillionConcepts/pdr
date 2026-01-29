import warnings


def get_special_block_grs_table(data):
    """
    GRS tables sometimes have the pointer not matching the object name.

    HITS
    * kaguya
        * grs_nmap_tables
    """
    object_name = "SPREADSHEET"
    block = data.metablock_(object_name)

    return block


def pace_time_series_trivial():
    """
    There is not enough info in the label or online to open this without more
    info.
    The "software" folder for this dataset contains read_pbf_v2.c for reading
    the datasets, but isn't currently implemented.
    HITS:
    * kaguya
        * IPACE_PBF1
    """
    warnings.warn(
        f"This product's TIME_SERIES pointer is not currently supported."
    )
    return True


def sp_l2d_result_array_trivial():
    """
    There is not enough info in the label or online to open this without more
    info.
    The label lists it as having 0 size.
    HITS:
    * kaguya
        * sp_2b2
        * sp_2b1
        * sp_2c
    """
    warnings.warn(
        f"This product's L2D_RESULT_ARRAY pointer is not currently supported."
    )
    return True


def get_special_block_sp_2b_supp(data, name):
    """
    The label includes columns not in the supplemental table for 2b products,
    only 2c. We remove them and correct the number of columns in the block.

    HITS:
    * kaguya
        * sp_2b2
        * sp_2b1
    """
    from multidict import MultiDict

    block = data.metablock_(name)
    keep_keys = list(block.items())[:-4]
    block = MultiDict(keep_keys)
    block["COLUMNS"] = block["COLUMNS"] - 4

    return block


def sp_tc_filename_pointer_trivial():
    """
    The QA_FILENAME pointer is to another file that has its own label, there
    is no object description in the DTM label for the QA .img file.

    HITS:
    * kaguya
        * tc_dem_ortho_v1_dtm
    """
    warnings.warn(
        f"The QA_FILENAME pointer is for a filename, not the actual QA object."
        f" Try loading via the QA file label or .img file."
    )
    return True


def grs_eng_tables_trivial():
    """
    The format of these tables is kind of complicated & not noted in the label.
    A recalibrated set of the GRS ENG tables supported by PDR is available in
    the PDS Geosciences node with PDS4 labels.

    HITS:
    * kaguya
        * grs_eng_tables
    """
    warnings.warn(
        f"These GRS energy tables have no object description in the label."
        f" A recalibrated set of the GRS ENG tables supported by PDR is "
        f"available in the PDS Geosciences node with PDS4 labels."
    )
    return True


def get_special_grid_table_block():
    """
    These tables have no column information in the object definition and
    what is there is wrong-- so we make our own block. There are only 3 tables,
    so we have checked that this applies to all MAG grid tables.

    Table info from LMAG_Format_en_V01.pdf.

    HITS:
    * kaguya
        * mag_grid_option
        * mag_grid_tables
    """
    from multidict import MultiDict

    block = MultiDict({
        "INTERCHANGE_FORMAT": "ASCII",
        "ROWS": 64440,
        "COLUMNS": 11,
        "ROW_BYTES": 96,
    })
    columns = [
        dict(
            NAME="LATITUDE",
            START_BYTE=1,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="DEGREE",
            DESCRIPTION="Latitude in a moon fixed ME coordinate",
        ),
        dict(
            NAME="LONGITUDE",
            START_BYTE=10,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="DEGREE",
            DESCRIPTION="Longitude in a moon fixed ME coordinate",
        ),
        dict(
            NAME="X",
            START_BYTE=19,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="X-component of the Magnetic Anomaly data",
        ),
        dict(
            NAME="Y",
            START_BYTE=28,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Y-component of the Magnetic Anomaly data",
        ),
        dict(
            NAME="Z",
            START_BYTE=37,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Z-component of the Magnetic Anomaly data",
        ),
        dict(
            NAME="F",
            START_BYTE=46,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="F-component (total magnetic intensity) of the "
                        "Magnetic Anomaly data",
        ),
        dict(
            NAME="X1",
            START_BYTE=55,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Standard Error of X-component of the Magnetic Anomaly"
                        " data",
        ),
        dict(
            NAME="Y2",
            START_BYTE=64,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Standard Error of Y-component of the Magnetic Anomaly"
                        " data",
        ),
        dict(
            NAME="Z2",
            START_BYTE=73,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Standard Error of Z-component of the Magnetic Anomaly"
                        " data",
        ),
        dict(
            NAME="F2",
            START_BYTE=82,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.2",
            UNIT="nT",
            DESCRIPTION="Standard Error of F-component of the Magnetic Anomaly"
                        " data",
        ),
        dict(
            NAME="A",
            START_BYTE=91,
            BYTES=4,
            DATA_TYPE="ASCII_INTEGER",
            FORMAT="I4",
            DESCRIPTION="Effective data for each grid",
        ),
    ]

    for col in columns:
        block.add("COLUMN", MultiDict(col))

    return block


def get_special_1d_sigma_block():
    """
    These tables have no column information in the object definition and
    what is there is wrong-- so we make our own block.

    Table info from LMAG_Format_en_V01.pdf.

    HITS:
    * kaguya
        * mag_sigma_table
    """
    from multidict import MultiDict

    block = MultiDict({
        "INTERCHANGE_FORMAT": "ASCII",
        "ROWS": 2,
        "COLUMNS": 3,
        "ROW_BYTES": 32,
    })

    columns = [
        dict(
            NAME="TOP_RADIUS",
            START_BYTE=1,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="km",
            DESCRIPTION="Top radius of the layer",
        ),
        dict(
            NAME="UNDER_RADIUS",
            START_BYTE=10,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="km",
            DESCRIPTION="Under radius of the layer",
        ),
        dict(
            NAME="ELECTRICAL_CONDUCTANCE",
            START_BYTE=19,
            BYTES=12,
            DATA_TYPE="ASCII_REAL",
            FORMAT="E12.3",
            UNIT="S/m",
            DESCRIPTION="Electrical conductance in the layer",
        ),
    ]

    for col in columns:
        block.add("COLUMN", MultiDict(col))

    return block


def get_special_mag_ts_block(data):
    """
    These tables have no column information in the object definition and
    what is there is wrong-- so we make our own block.
    Table info from LMAG_Format_en_V01.pdf.

    HITS:
    * kaguya
        * mag_ts_table
    """
    from multidict import MultiDict

    # table pointer has matching object called TIME_SERIES
    block = data.metablock_("TIME_SERIES")

    block = MultiDict({
        "INTERCHANGE_FORMAT": "ASCII",
        "ROWS": block["ROWS"],
        "COLUMNS": 13,
        "ROW_BYTES": 129,
        "SAMPLING_PARAMETER_NAME": "TIME",
        "SAMPLING_PARAMETER_UNIT": "SECOND",
        "SAMPLING_PARAMETER_INTERVAL": 4.0,
    })

    columns = [
        dict(
            NAME="TIME",
            START_BYTE=1,
            BYTES=19,
            DATA_TYPE="ASCII_CHAR",
            FORMAT="YYYY-MM-DDThh:mm:ss",
            DESCRIPTION="Time Information",
        ),
        dict(
            NAME="X1",
            START_BYTE=21,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="km",
            DESCRIPTION="X-coordinate of the satellite position at the moon "
                        "center fixed ME coordinate system",
        ),
        dict(
            NAME="Y1",
            START_BYTE=30,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="km",
            DESCRIPTION="Y-coordinate of the satellite position at the moon "
                        "center fixed ME coordinate system",
        ),
        dict(
            NAME="Z1",
            START_BYTE=39,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F8.1",
            UNIT="km",
            DESCRIPTION="Z-coordinate of the satellite position at the moon "
                        "center fixed ME coordinate system",
        ),
        dict(
            NAME="Bx1",
            START_BYTE=48,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="X-component of the magnetic field at the moon center "
                        "fixed ME coordinate system",
        ),
        dict(
            NAME="By1",
            START_BYTE=56,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="Y-component of the magnetic field at the moon center "
                        "fixed ME coordinate system",
        ),
        dict(
            NAME="Bz1",
            START_BYTE=64,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="Z-component of the magnetic field at the moon center"
                        " fixed ME coordinate system",
        ),
        dict(
            NAME="X2",
            START_BYTE=72,
            BYTES=10,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F10.1",
            UNIT="km",
            DESCRIPTION="X-coordinate of the satellite position in GSE",
        ),
        dict(
            NAME="Y2",
            START_BYTE=83,
            BYTES=10,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F10.1",
            UNIT="km",
            DESCRIPTION="Y-coordinate of the satellite position in GSE",
        ),
        dict(
            NAME="Z2",
            START_BYTE=94,
            BYTES=10,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F10.1",
            UNIT="km",
            DESCRIPTION="Z-coordinate of the satellite position in GSE",
        ),
        dict(
            NAME="Bx2",
            START_BYTE=105,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="X-component of the magnetic field in GSE",
        ),
        dict(
            NAME="By2",
            START_BYTE=113,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="Y-component of the magnetic field in GSE",
        ),
        dict(
            NAME="Bz2",
            START_BYTE=121,
            BYTES=7,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F7.2",
            UNIT="nT",
            DESCRIPTION="Z-component of the magnetic field in GSE",
        ),
    ]

    for col in columns:
        block.add("COLUMN", MultiDict(col))

    return block


def rise_traj_special_block():
    """
    These tables have no column information in the object definition and
    what is there is wrong-- so we make our own block.
    Table info from RV_Format_en_V01.pdf.

    HITS:
    * kaguya
        * rise_traj_table
    """
    from multidict import MultiDict

    block = MultiDict({
        "INTERCHANGE_FORMAT": "ASCII",
        "COLUMNS": 12,
        "ROW_BYTES": 133,
        "OBJECT_TYPE": "SERIES",
    })

    columns = [
        dict(
            NAME="DATE",
            START_BYTE=2,
            BYTES=6,
            DATA_TYPE="ASCII_CHAR",
            FORMAT="YYMMDD",
            DESCRIPTION="Date",
        ),
        dict(
            NAME="GREENWICH_TIME_HHMM",
            START_BYTE=9,
            BYTES=4,
            DATA_TYPE="ASCII_CHAR",
            FORMAT="hhmm",
            DESCRIPTION="Greenwich Time (hour and minute UT)",
        ),
        dict(
            NAME="GREENWICH_TIME_SS",
            START_BYTE=15,
            BYTES=8,
            DATA_TYPE="ASCII_REAL",
            FORMAT="s.ssssss",
            UNIT="Second (UT)",
            DESCRIPTION="Greenwich Time seconds",
        ),
        dict(
            NAME="X",
            START_BYTE=23,
            BYTES=13,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F13.2",
            UNIT="m",
            DESCRIPTION="X-coordinate (Inertial Cartesian)",
        ),
        dict(
            NAME="Y",
            START_BYTE=36,
            BYTES=13,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F13.2",
            UNIT="m",
            DESCRIPTION="Y-coordinate (Inertial Cartesian)",
        ),
        dict(
            NAME="Z",
            START_BYTE=49,
            BYTES=13,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F13.2",
            UNIT="m",
            DESCRIPTION="Z-coordinate (Inertial Cartesian)",
        ),
        dict(
            NAME="VX",
            START_BYTE=62,
            BYTES=12,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F12.5",
            UNIT="m/s",
            DESCRIPTION="X-component of inertial velocity",
        ),
        dict(
            NAME="VY",
            START_BYTE=74,
            BYTES=12,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F12.5",
            UNIT="m/s",
            DESCRIPTION="Y-component of inertial velocity",
        ),
        dict(
            NAME="VZ",
            START_BYTE=86,
            BYTES=12,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F12.5",
            UNIT="m/s",
            DESCRIPTION="Z-component of inertial velocity",
        ),
        dict(
            NAME="LAT",
            START_BYTE=98,
            BYTES=11,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F11.6",
            UNIT="deg",
            DESCRIPTION="Geodetic North Latitude",
        ),
        dict(
            NAME="LON",
            START_BYTE=109,
            BYTES=11,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F11.6",
            UNIT="deg",
            DESCRIPTION="Geodetic East Longitude",
        ),
        dict(
            NAME="HEIGHT",
            START_BYTE=120,
            BYTES=13,
            DATA_TYPE="ASCII_REAL",
            FORMAT="F13.2",
            UNIT="m",
            DESCRIPTION="Spheroidal height",
        ),
    ]

    for col in columns:
        block.add("COLUMN", MultiDict(col))

    return block
