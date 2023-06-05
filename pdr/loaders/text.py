import warnings
from typing import Optional

from pdr.loaders.utility import looks_like_this_kind_of_file
from pdr.parselabel.utils import trim_label
from pdr.utils import check_cases, decompress


def read_text(target, fn):
    try:
        if isinstance(fn, str):
            return ignore_if_pdf(check_cases(fn))
        elif isinstance(fn, list):
            return [
                ignore_if_pdf(check_cases(each_file))
                for each_file in fn
            ]
    except FileNotFoundError or UnicodeDecodeError:
        warnings.warn(f"couldn't find {target}")
        raise
    except Exception:
        raise


def read_header(fn, table_props, name="HEADER"):
    """Attempt to read a file header."""
    return skeptically_load_header(fn, table_props, name)


def read_label(fn, fmt: Optional[str] = "text"):
    if fmt == "text":
        return trim_label(decompress(fn)).decode("utf-8")
    elif fmt == "pvl":
        import pvl

        return pvl.load(fn)
    raise NotImplementedError(f"The {fmt} format is not yet implemented.")


def skeptically_load_header(
    fn,
    table_props,
    name="header",
    fmt: Optional[str] = "text",
):
    # TODO: all these check_cases calls are probably unnecessary w/new file
    #  mapping workflow
    try:
        if fmt == "pvl":
            try:
                from pdr.pvl_utils import cached_pvl_load

                return cached_pvl_load(decompress(check_cases(fn)))
            except ValueError:
                pass
        if table_props["as_rows"] is True:
            with decompress(check_cases(fn)) as file:
                if table_props["start"] > 0:
                    file.readlines(table_props["start"])
                text = "\r\n".join(
                    map(
                        lambda l: l.decode("utf-8"),
                        file.readlines(table_props["length"]),
                    )
                )
        else:
            with decompress(check_cases(fn)) as file:
                file.seek(table_props["start"])
                text = file.read(min(table_props["length"], 80000)).decode(
                    "ISO-8859-1"
                )
        return text
    except (ValueError, OSError) as ex:
        warnings.warn(f"unable to parse {name}: {ex}")


def ignore_if_pdf(fn):
    if looks_like_this_kind_of_file(fn, [".pdf"]):
        warnings.warn(f"Cannot open {fn}; PDF files are not supported.")
        return
    return open(check_cases(fn)).read()
