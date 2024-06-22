from pathlib import Path


def get_fn(data):
    """
    The PEPSSI DDRs have an extra space at the start of the SPREADSHEET
    pointer's filename that causes 'file not found' errors.

    HITS
    * nh_derived
        * atmos_comp
    * nh_pepssi
        * flux_resampled
    """
    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.csv")
