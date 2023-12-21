from tkinter import filedialog
from os import getcwd
import zpaqtreeview as ztv
import sys
import logging
import argparse
import threading
from functools import wraps
from pathlib import Path, PureWindowsPath

from winfspy import (
    FileSystem,
    BaseFileSystemOperations,
    enable_debug_log,
    FILE_ATTRIBUTE,
    CREATE_FILE_CREATE_OPTIONS,
    NTStatusObjectNameNotFound,
    NTStatusDirectoryNotEmpty,
    NTStatusNotADirectory,
    NTStatusObjectNameCollision,
    NTStatusAccessDenied,
    NTStatusEndOfFile,
    NTStatusMediaWriteProtected,
)
from winfspy.plumbing.win32_filetime import filetime_now
from winfspy.plumbing.security_descriptor import SecurityDescriptor
from tqdm import tqdm


def operation(fn):
    """Decorator for file system operations.

    Provides both logging and thread-safety
    """
    name = fn.__name__

    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        head = args[0] if args else None
        tail = args[1:] if args else ()
        try:
            with self._thread_lock:
                result = fn(self, *args, **kwargs)
        except Exception as exc:
            logging.info(f" NOK | {name:20} | {head!r:20} | {tail!r:20} | {exc!r}")
            raise
        else:
            logging.info(f" OK! | {name:20} | {head!r:20} | {tail!r:20} | {result!r}")
            return result

    return wrapper


class BaseFileObj:
    @property
    def name(self):
        """File name, without the path"""
        return self.path.name

    @property
    def file_name(self):
        """File name, including the path"""
        return str(self.path)

    def __init__(self, path, attributes, security_descriptor, file_data):
        self.path = path
        self.file_data = file_data
        self.attributes = attributes
        self.security_descriptor = security_descriptor
        now = filetime_now()
        self.creation_time = now
        self.last_access_time = now
        self.last_write_time = now
        self.change_time = now
        self.index_number = 0
        self.file_size = 0

    def get_file_info(self):
        return {
            "file_attributes": self.attributes,
            "allocation_size": self.allocation_size,
            "file_size": self.file_size,
            "creation_time": self.creation_time,
            "last_access_time": self.last_access_time,
            "last_write_time": self.last_write_time,
            "change_time": self.change_time,
            "index_number": self.index_number,
        }

    def __repr__(self):
        return f"{type(self).__name__}:{self.file_name}"


class FileObj(BaseFileObj):

    allocation_unit = 4096

    def __init__(self, path, attributes, security_descriptor, file_data, allocation_size=0):
        super().__init__(path, attributes, security_descriptor, file_data)
        self.data = bytearray(allocation_size)
        self.attributes |= FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE
        assert not self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY

    @property
    def allocation_size(self):
        return len(self.data)

    def set_allocation_size(self, allocation_size):
        if allocation_size < self.allocation_size:
            self.data = self.data[:allocation_size]
        if allocation_size > self.allocation_size:
            self.data += bytearray(allocation_size - self.allocation_size)
        assert self.allocation_size == allocation_size
        self.file_size = min(self.file_size, allocation_size)

    def adapt_allocation_size(self, file_size):
        units = (file_size + self.allocation_unit - 1) // self.allocation_unit
        self.set_allocation_size(units * self.allocation_unit)

    def set_file_size(self, file_size):
        if file_size < self.file_size:
            zeros = bytearray(self.file_size - file_size)
            self.data[file_size : self.file_size] = zeros
        if file_size > self.allocation_size:
            self.adapt_allocation_size(file_size)
        self.file_size = file_size

    def read(self, offset, length):
        if offset >= self.file_size:
            raise NTStatusEndOfFile()
        end_offset = min(self.file_size, offset + length)
        return self.data[offset:end_offset]


class FolderObj(BaseFileObj):
    def __init__(self, path, attributes, security_descriptor, file_data):
        super().__init__(path, attributes, security_descriptor, file_data)
        self.allocation_size = 0
        assert self.attributes & FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY


class OpenedObj:
    def __init__(self, file_obj):
        self.file_obj = file_obj

    def __repr__(self):
        return f"{type(self).__name__}:{self.file_obj.file_name}"


class ZpaqFileSystemOperations(BaseFileSystemOperations):

    def __init__(self, volume_label, input_file, cache_location, max_cache_size, config, read_only=False):
        super().__init__()
        if len(volume_label) > 31:
            raise ValueError("`volume_label` must be 31 characters long max")

        max_file_nodes = 1024
        max_file_size = 16 * 1024 * 1024
        file_nodes = 1

        self._volume_info = {
            "total_size": max_file_nodes * max_file_size,
            "free_size": 0, #(max_file_nodes - file_nodes) * max_file_size,
            "volume_label": volume_label,
        }

        self.input_file = input_file
        self.max_cache_size = max_cache_size
        self.config = config
        self.cache_location = PureWindowsPath(cache_location)
        self.read_only = read_only
        self._root_path = PureWindowsPath("/")
        self._root_obj = FolderObj(
            self._root_path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
            SecurityDescriptor.from_string("O:BAG:BAD:P(A;;FA;;;SY)(A;;FA;;;BA)(A;;FA;;;WD)"), None
        )
        self._entries = {self._root_path: self._root_obj}
        self._thread_lock = threading.Lock()

    # Debugging helpers

    def _create_directory(self, path, file_data):
        path = self._root_path / path
        obj = FolderObj(
            path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY,
            self._root_obj.security_descriptor,
            file_data
        )
        self._entries[path] = obj

    def _import_files(self, file_path, file_data):
        file_path = Path(file_path)
        path = self._root_path / file_path.name
        obj = FileObj(
            path,
            FILE_ATTRIBUTE.FILE_ATTRIBUTE_ARCHIVE,
            file_data,
            self._root_obj.security_descriptor,
        )
        self._entries[path] = obj
        obj.write(file_path.read_bytes(), 0, False)

    # Winfsp operations

    @operation
    def get_volume_info(self):
        return self._volume_info

    @operation
    def set_volume_label(self, volume_label):
        self._volume_info["volume_label"] = volume_label

    @operation
    def get_security_by_name(self, file_name):
        file_name = PureWindowsPath(file_name)

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return (
            file_obj.attributes,
            file_obj.security_descriptor.handle,
            file_obj.security_descriptor.size,
        )

    @operation
    def create(
        self,
        file_name,
        create_options,
        granted_access,
        file_attributes,
        security_descriptor,
        allocation_size,
        file_data,
    ):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_name = PureWindowsPath(file_name)

        # `granted_access` is already handle by winfsp
        # `allocation_size` useless for us

        # Retrieve file
        try:
            parent_file_obj = self._entries[file_name.parent]
            if isinstance(parent_file_obj, FileObj):
                raise NTStatusNotADirectory()
        except KeyError:
            raise NTStatusObjectNameNotFound()

        # File/Folder already exists
        if file_name in self._entries:
            raise NTStatusObjectNameCollision()

        if create_options & CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE:
            file_obj = self._entries[file_name] = FolderObj(
                file_name, file_attributes, security_descriptor, file_data
            )
        else:
            file_obj = self._entries[file_name] = FileObj(
                file_name,
                file_attributes,
                security_descriptor,
                file_data,
                allocation_size,
            )

        return OpenedObj(file_obj)

    @operation
    def get_security(self, file_context):
        return file_context.file_obj.security_descriptor

    @operation
    def set_security(self, file_context, security_information, modification_descriptor):
        raise NotImplementedError()

    @operation
    def rename(self, file_context, file_name, new_file_name, replace_if_exists):
        raise NotImplementedError()

    @operation
    def open(self, file_name, create_options, granted_access):
        file_name = PureWindowsPath(file_name)

        # `granted_access` is already handle by winfsp

        # Retrieve file
        try:
            file_obj = self._entries[file_name]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return OpenedObj(file_obj)

    @operation
    def close(self, file_context):
        pass

    @operation
    def get_file_info(self, file_context):
        return file_context.file_obj.get_file_info()

    @operation
    def set_basic_info(
        self,
        file_context,
        file_attributes,
        creation_time,
        last_access_time,
        last_write_time,
        change_time,
        file_info,
    ) -> dict:
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        file_obj = file_context.file_obj
        if file_attributes != FILE_ATTRIBUTE.INVALID_FILE_ATTRIBUTES:
            file_obj.attributes = file_attributes
        if creation_time:
            file_obj.creation_time = creation_time
        if last_access_time:
            file_obj.last_access_time = last_access_time
        if last_write_time:
            file_obj.last_write_time = last_write_time
        if change_time:
            file_obj.change_time = change_time

        return file_obj.get_file_info()

    @operation
    def set_file_size(self, file_context, new_size, set_allocation_size):
        if self.read_only:
            raise NTStatusMediaWriteProtected()

        if set_allocation_size:
            file_context.file_obj.set_allocation_size(new_size)
        else:
            file_context.file_obj.set_file_size(new_size)

    @operation
    def can_delete(self, file_context, file_name: str) -> None:
        raise NotImplementedError()

    @operation
    def read_directory(self, file_context, marker):
        entries = []
        file_obj = file_context.file_obj

        # Not a directory
        if isinstance(file_obj, FileObj):
            raise NTStatusNotADirectory()

        # The "." and ".." should ONLY be included if the queried directory is not root
        if file_obj.path != self._root_path:
            parent_obj = self._entries[file_obj.path.parent]
            entries.append({"file_name": ".", **file_obj.get_file_info()})
            entries.append({"file_name": "..", **parent_obj.get_file_info()})

        # Loop over all entries
        for entry_path, entry_obj in self._entries.items():
            try:
                relative = entry_path.relative_to(file_obj.path)
            # Filter out unrelated entries
            except ValueError:
                continue
            # Filter out ourself or our grandchildren
            if len(relative.parts) != 1:
                continue
            # Add direct chidren to the entry list
            entries.append({"file_name": entry_path.name, **entry_obj.get_file_info()})

        # Sort the entries
        entries = sorted(entries, key=lambda x: x["file_name"])

        # No filtering to apply
        if marker is None:
            return entries

        # Filter out all results before the marker
        for i, entry in enumerate(entries):
            if entry["file_name"] == marker:
                return entries[i + 1 :]

    @operation
    def get_dir_info_by_name(self, file_context, file_name):
        path = file_context.file_obj.path / file_name
        try:
            entry_obj = self._entries[path]
        except KeyError:
            raise NTStatusObjectNameNotFound()

        return {"file_name": file_name, **entry_obj.get_file_info()}

    @operation
    def read(self, file_context, offset, length):
        if file_context.file_obj.file_size < self.max_cache_size: # 5 MB
            ztv.extract_file(config, self.input_file, file_context.path,
                             self.cache_location, file_context.file_obj.file_data.is_directory())

        return -1 #ile_context.file_obj.read(offset, length)

    @operation
    def write(self, file_context, buffer, offset, write_to_end_of_file, constrained_io):
        raise NotImplementedError()

    @operation
    def cleanup(self, file_context, file_name, flags) -> None:
        raise NotImplementedError()

    @operation
    def overwrite(
        self, file_context, file_attributes, replace_file_attributes: bool, allocation_size: int
    ) -> None:
        raise NotImplementedError()

    @operation
    def flush(self, file_context) -> None:
        pass


def create_memory_file_system(
    mountpoint, label="memfs", prefix="", verbose=True, debug=False, testing=False,
        input_file="", cache_location="%userprofile%/AppData/Local/", max_cache_size = 30 * 10^6 , config=None):
    if debug:
        enable_debug_log()

    if verbose:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    # The avast workaround is not necessary with drives
    # Also, it is not compatible with winfsp-tests
    mountpoint = Path(mountpoint)
    is_drive = mountpoint.parent == mountpoint
    reject_irp_prior_to_transact0 = not is_drive and not testing

    operations = ZpaqFileSystemOperations(label, input_file, cache_location, max_cache_size, config)
    fs = FileSystem(
        str(mountpoint),
        operations,
        sector_size=512,
        sectors_per_allocation_unit=1,
        volume_creation_time=filetime_now(),
        volume_serial_number=0,
        file_info_timeout=1000,
        case_sensitive_search=1,
        case_preserved_names=1,
        unicode_on_disk=1,
        persistent_acls=1,
        post_cleanup_when_modified_only=1,
        um_file_context_is_user_context2=1,
        file_system_name=str(mountpoint),
        prefix=prefix,
        debug=debug,
        reject_irp_prior_to_transact0=reject_irp_prior_to_transact0,
        # security_timeout_valid=1,
        # security_timeout=10000,
    )
    return fs

def convert_filetree(config, file_path, fs):
    tl_tree = ztv.main(config, file_path)
    tl_node_stack = [tl_tree.get_node(tl_tree.root)]

    new_path = tl_tree.get_node(tl_tree.root).data.fullPath.replace(tl_tree.root, fs.mountpoint) + "/"
    print("In convert before first create.")
    # fs_root = fs.operations.create(new_path, CREATE_FILE_CREATE_OPTIONS.FILE_DIRECTORY_FILE, None,
    #                      FILE_ATTRIBUTE.FILE_ATTRIBUTE_DIRECTORY, None, 0, tl_tree.get_node(tl_tree.root).data)
    # fs_stack = [fs_root]
    # fs_root = fs.operations._create_directory(new_path, tl_tree.get_node(tl_tree.root).data)

    print("Converting file tree to textual...")
    bar = tqdm(total=tl_tree.size(), unit="nodes", colour="green", leave=False)
    c1 = 0
    while len(tl_node_stack) > 0:
        tl_node = tl_node_stack.pop()
        # fs_node = fs_stack.pop()

        #children_sorted = tl_tree.children(tl_node.tag)
        #children_sorted.sort(key=lambda x: (x.is_leaf(), x.data.name.lower()))  # TODO: check if necessary to sort
        if (tl_node.data.is_directory()):
            for tl_child_node in tl_tree.children(tl_node.tag):  # children_sorted:
                new_path = tl_child_node.data.fullPath.replace(tl_tree.root, "")
                if (tl_child_node.data.is_directory()): # is directory
                    tl_node_stack.append(tl_child_node)
                    fs.operations._create_directory(new_path, tl_child_node.data)
                else: # is file
                    fileobj = fs.operations.create(new_path, CREATE_FILE_CREATE_OPTIONS.FILE_NON_DIRECTORY_FILE, None,
                        FILE_ATTRIBUTE.FILE_ATTRIBUTE_NORMAL, fs.operations._root_obj.security_descriptor, 0, tl_child_node.data)
                    fileobj.file_obj.set_file_size(tl_child_node.data.size)

        bar.update()


    bar.close()

def create_filesystem(mountpoint, label, prefix, verbose, debug, input_file, cache_location, max_cache_size):
    config = ztv.load_create_config()
    print(f"Input file: {input_file}")
    fs = create_memory_file_system(mountpoint, label, prefix, verbose, debug, False,
                                   input_file, cache_location, max_cache_size, config,)
    try:
        print("Starting FS")
        fs.start()
        print("FS started, keep it running forever")
        # while True:
        #     result = input("Set read-only flag (y/n/q)? ").lower()
        #     if result == "y":
        #         fs.operations.read_only = True
        #         fs.restart(read_only_volume=True)
        #     elif result == "n":
        #         fs.operations.read_only = False
        #         fs.restart(read_only_volume=False)
        #     elif result == "q":
        #         break
        print(f"Input file: {fs.operations.input_file}")
        convert_filetree(config, fs.operations.input_file, fs)
        fs.read_only = True
        fs.restart(read_only_volume=True)
        input("press enter to exit")

    finally:
        print("Stopping FS")
        fs.stop()
        print("FS stopped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mountpoint")
    parser.add_argument("-z", "--zpaq", type=str, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-l", "--label", type=str, default="memfs")
    parser.add_argument("-p", "--prefix", type=str, default="")
    parser.add_argument("-c", "--cache-location", type=str, default="%userprofile%/AppData/Local/Temp")
    parser.add_argument("-s", "--cache-size-limit", type=int, default=30 * 10^6) # 30 MB
    args = parser.parse_args()

    if args.zpaq is None:
        input_file = None
        while input_file is None:
            input_file = filedialog.askopenfilename(initialdir=getcwd(), title="Select a zpaq file")

        args.zpaq = input_file

    create_filesystem(args.mountpoint, args.label, args.prefix, args.verbose,
                      args.debug, args.zpaq, args.cache_location, args.cache_size_limit)



if __name__ == "__main__":
    main()