import warnings

from pdr.loaders.handlers import handle_fits_file
from pdr.loaders.utility import looks_like_this_kind_of_file, FITS_EXTENSIONS
from pdr.parselabel.pds3 import pointerize
from pdr.parselabel.utils import trim_label
from pdr.utils import check_cases, decompress


def read_text(self, object_name):
    target = self.metaget_(pointerize(object_name))
    local_path = self.file_mapping[object_name]
    try:
        if isinstance(local_path, str):
            return ignore_if_pdf(self, object_name, check_cases(local_path))
        elif isinstance(local_path, list):
            return [
                ignore_if_pdf(self, object_name, check_cases(each_local_path))
                for each_local_path in local_path
            ]
    except FileNotFoundError as ex:
        exception = ex
        warnings.warn(f"couldn't find {target}")
    except UnicodeDecodeError as ex:
        exception = ex
        warnings.warn(f"couldn't parse {target}")
    except Exception:
        raise
    return self._catch_return_default(object_name, exception)


def read_header(self, object_name="HEADER"):
    """Attempt to read a file header."""
    if looks_like_this_kind_of_file(
        self.file_mapping[object_name], FITS_EXTENSIONS
    ):
        return handle_fits_file(object_name)
    start, length, as_rows = self.table_position(object_name)
    return skeptically_load_header(
        self.file_mapping[object_name], object_name, start, length, as_rows
    )


def read_label(labelname, _pointer, fmt="text"):
    if fmt == "text":
        return trim_label(decompress(labelname)).decode("utf-8")
    elif fmt == "pvl":
        import pvl

        return pvl.load(labelname)
    raise NotImplementedError(f"The {fmt} format is not yet implemented.")


def skeptically_load_header(
    path,
    object_name="header",
    start=0,
    length=None,
    as_rows=False,
    as_pvl=False,
):
    # TODO: all these check_cases calls are probably unnecessary w/new file
    #  mapping workflow
    try:
        if as_pvl is True:
            try:
                from pdr.pvl_utils import cached_pvl_load

                return cached_pvl_load(decompress(check_cases(path)))
            except ValueError:
                pass
        if as_rows is True:
            with decompress(check_cases(path)) as file:
                if start > 0:
                    file.readlines(start)
                text = "\r\n".join(
                    map(lambda l: l.decode('utf-8'), file.readlines(length))
                )
        else:
            with decompress(check_cases(path)) as file:
                file.seek(start)
                text = file.read(min(length, 80000)).decode('ISO-8859-1')
        return text
    except (ValueError, OSError) as ex:
        warnings.warn(f"unable to parse {object_name}: {ex}")


def ignore_if_pdf(data, object_name, path):
    if looks_like_this_kind_of_file(path, [".pdf"]):
        warnings.warn(
            f"Cannot open {path}; PDF files are not supported."
        )
        block = data.metaget_(object_name)
        if block is None:
            return data.metaget_(pointerize(object_name))
        return block
    return open(check_cases(path)).read()
