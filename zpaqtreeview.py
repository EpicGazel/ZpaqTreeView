from treelib import Tree
import re
from subprocess import check_output, Popen, PIPE, CalledProcessError
import tqdm
from sys import stderr


class File:
    def __init__(self, full_path, size, last_modified, attribute):
        self.fullPath = full_path.rstrip("/")
        self.size = size
        self.lastModified = last_modified
        self.attribute = attribute
        if full_path[-1] != "/":  # not a folder
            self.name = full_path.split("/")[-1]
        else:
            self.name = full_path.split("/")[-2]

    def __str__(self):
        return f"{self.lastModified}\t{self.size:>14} {self.attribute:10}\t {self.fullPath}"


def is_directory(node):
    return not node.is_leaf()


def build_parent_nodes(tree: Tree, path: str):
    parent_path = '/'.join(path.split('/')[0:-1])

    if parent_path.find('/') == -1:
        if not tree.get_node(parent_path):  # parent is root
            data = File(parent_path, 0, 0, "root")
            tree.create_node(parent_path, parent_path, data=data)
        return parent_path

    if not tree.get_node(parent_path):
        tree.create_node(parent_path, parent_path, parent=build_parent_nodes(tree, parent_path))

    return parent_path


def add_node_new(tree: Tree, node: File):
    build_parent_nodes(tree, node.fullPath)
    if tree.get_node(node.fullPath):
        tree.get_node(node.fullPath).data = node
        return

    parent_path = node.fullPath[0:-(len(node.name) + 1)]
    tree.create_node(node.fullPath, node.fullPath, parent=parent_path, data=node)
    return


def create_filetree(tree: Tree, contents):
    pattern = re.compile(
        r"-\s(?P<daytime>[0-9]{4}-[0-9]{2}-[0-9]{2}\s[0-9]{2}:[0-9]{2}:[0-9]{2})\s+"
        r"(?P<size>[0-9]+(\.[0-9]+)*)\s+(?P<attribute>[A-Za-z0-9]+)\s+(?P<path>.*)")
    num_files_pattern = re.compile(r"([0-9]+(\.[0-9])*)+\sfiles")

    num_files = 0
    for line in contents:
        match = re.search(num_files_pattern, line)
        if match:
            temp = match.group()
            num_files = int(temp[0:temp.find(" files")].replace(".", ""))
            break
        elif line.find("ERROR_FILE_NOT_FOUND") != -1:
            print("ZPAQ file not found.", file=stderr)
            exit(1)
        elif line.find("Usage") != -1:
            print("ZPAQ path may have been entered improperly.", file=stderr)
            exit(1)

    for line in tqdm.tqdm(contents, total=num_files, unit="files", colour="green"):
        try:
            if line[0] == "-":
                line = line.rstrip()
                date, _, __, attribute, fullpath = re.search(pattern, line).groups()
                size = re.search(pattern, line).group("size")
                testfile = File(fullpath, size, date, attribute)
                add_node_new(tree, testfile)
            else:
                pass  # print("No match found.")
        except IndexError:  # sometimes line[0] is invalid
            pass


def explore_tree(tree: Tree, zpaqpath: str = None):
    user_input = "0"
    curr_node = tree.root
    while user_input != 'q' and user_input != 'Q':
        print(f"Current node: {curr_node}")
        if len(tree.children(curr_node)) == 0:
            print("Node empty.")
            print("Enter .. to go back a directory. Enter root to go back to "
                  "root.\nEnter s to save tree to file.\nEnter x to extract file/directory.\nEnter q to quit")
        else:
            for index, node in enumerate(tree.children(curr_node)):
                print(f"{index + 1:>4}: {node.data}")
            print("Enter a node number to explore it.\nEnter .. to go back a directory. Enter root to go back to "
                  "root.\nEnter s to save tree to file.\nEnter x to extract file/directory.\nEnter q to quit")

        user_input = input()
        if user_input == 'q' or user_input == 'Q':
            break
        elif user_input == 's':
            file_type = input("Enter text or json: ")
            path = input("Enter path: ")
            try:
                if file_type == "text":
                    tree.save2file(path)
                elif file_type == "json":
                    open(path, 'w').write(tree.to_json())
                else:
                    print("Invalid file type selected.")
            except Exception as e:  # FileNotFoundError, OSError Invalid argument,
                print(f"Something went wrong with the file path. Error: {e}")
            continue
        elif user_input.isnumeric() and 0 < int(user_input) <= len(tree.children(curr_node)):
            curr_node = tree.children(curr_node)[int(user_input) - 1].identifier
            continue
        elif user_input == '..':
            if tree.parent(curr_node) is not None:
                curr_node = tree.parent(curr_node).identifier
            else:
                print("Already at root.")
            continue
        elif user_input == 'root':
            curr_node = tree.root
            continue
        elif user_input == 'x':
            if zpaqpath is None:
                zpaqpath = input("Please specify path to zpaq file: ")
            extract_path = input("Enter extract path (not including file/directory name): ").replace("\\", "/")
            if len(tree.children(curr_node)) != 0: #tree.get_node(curr_node).data.size == '0':  # is folder, assumes all folders are 0 size
                if extract_path[-1] != "/":  # must include trailing /
                    extract_path += "/"
                command = f"zpaqfranz x \"{zpaqpath}\" \"{curr_node}/\" -to \"{extract_path}\" -longpath -find \"{curr_node}/\""
            else:  # is file or empty directory
                if extract_path[-1] == "/":  # must drop trailing /
                    extract_path = extract_path[:-1]
                command = f"zpaqfranz x \"{zpaqpath}\" \"{curr_node}\" -to \"{extract_path}\" -longpath -find \"{'/'.join(curr_node.split('/')[:-1])}/\""
                if extract_path[-1] == ":":  # when extracting to directory root, -space is required for some reason
                    command += " -space"

            print(f"Command: {command}")
            try:
                print(check_output(command).decode("utf-8"))
            except CalledProcessError as e:
                print(f"Something went wrong with extracting. Error: {e}")
        else:
            print("Invalid input. Please try again.")
            continue


def main():
    file_path = input("Enter file path to load: ")
    ext = file_path.split('.')[-1]
    zpaqpath = None
    try:
        if ext == 'zpaq':
            contents = Popen(["zpaqfranz", "l", file_path, "-longpath"], stdout=PIPE, encoding="utf-8",
                             errors="ignore").stdout
            zpaqpath = file_path
        elif ext == 'txt':
            contents = open(file_path, 'r', encoding="utf-8")
        else:
            print("Invalid file type.", file=stderr)
            exit(1)
    except Exception as e:
        print(f"Something went wrong getting the file list. Error: {e}", file=stderr)
        exit(1)

    tree = Tree()
    try:
        create_filetree(tree, contents)
    except Exception as e:
        print(f"Something went wrong creating the file tree. Error: {e}", file=stderr)
        if ext == 'txt':
            contents.close()
        exit(1)

    if ext == 'txt':
        contents.close()

    if __name__ == "__main__":
        try:
            explore_tree(tree, zpaqpath)
        except Exception as e:
            print(f"Something went wrong exploring the file tree. Error: {e}", file=stderr)
            exit(1)
    else:
        return tree


if __name__ == "__main__":
    main()
