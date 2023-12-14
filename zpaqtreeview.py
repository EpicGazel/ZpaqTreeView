# import sys
from treelib import Tree
import re
from subprocess import check_output, Popen, PIPE
import tqdm
# import time


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


def build_parent_nodes(tree: Tree, path: str):
    parent_path = '/'.join(path.split('/')[0:-1])

    if parent_path.find('/') == -1:
        if not tree.get_node(parent_path):
            tree.create_node(parent_path, parent_path)
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

    # TODO: Add progress loading bar
    bar = tqdm.tqdm(contents, total=99999)
    for line in bar:
        try:
            if num_files == 0:
                match = re.search(num_files_pattern, line)
                if match:
                    temp = match.group()
                    num_files = int(temp[0:temp.find(" files")].replace(".", ""))
                    bar.reset(total=num_files)
                    bar.refresh()
            elif line[0] == "-":
                line = line.rstrip()
                date, _, __, attribute, fullpath = re.search(pattern, line).groups()
                size = re.search(pattern, line).group("size")

                testfile = File(fullpath, size, date, attribute)
                # print(testfile)
                # print()
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
            path = input("Enter path: ")
            file_type = input("Enter text or json: ")
            if file_type == "text":
                tree.save2file(path)
            elif file_type == "json":
                open(path, 'w').write(tree.to_json())
            continue
        elif user_input.isnumeric():
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
            if tree.get_node(curr_node).data.size == '0':  # is folder, assumes all folders are 0 size
                if extract_path[-1] != "/":  # must include trailing /
                    extract_path += "/"
                command = f"zpaqfranz x \"{zpaqpath}\" \"{curr_node}/\" -to \"{extract_path}\" -longpath -find \"{curr_node}/\""
            else:  # is file
                if extract_path[-1] == "/":  # must drop trailing /
                    extract_path = extract_path[:-1]
                command = f"zpaqfranz x \"{zpaqpath}\" \"{curr_node}\" -to \"{extract_path}\" -longpath -find \"{'/'.join(curr_node.split('/')[:-1])}/\""
                if extract_path[-1] == ":":  # when extracting to directory root, -space is required for some reason
                    command += " -space"

            # print(f"Command: {command}")
            print(check_output(command).decode("utf-8"))
        else:
            print("Invalid input. Please try again.")
            continue


def main():
    file_path = input("Enter file path to load: ")
    ext = file_path.split('.')[-1]
    zpaqpath = None
    if ext == 'zpaq':
        # contents = check_output("zpaqfranz l \"" + file_path + "\" -longpath", encoding="utf-8", errors="ignore").split("\n")
        # start = time.time()
        contents = Popen(["zpaqfranz", "l", file_path, "-longpath"], stdout=PIPE, encoding="utf-8", errors="ignore").stdout
        zpaqpath = file_path
        # for line in contents:
        #     print(line.rstrip())
        # open("testoutput.txt", 'w', encoding="utf-8").write(contents)
    elif ext == 'txt':
        contents = open(file_path, 'r', encoding="utf-8")
    else:
        print("Invalid file type. Please try again.")
        return

    tree = Tree()
    create_filetree(tree, contents)
    # print(f"Tree created in {round(time.time() - start, 2)} seconds.")
    # return

    if ext == 'txt':
        contents.close()

    explore_tree(tree, zpaqpath)


if __name__ == "__main__":
    main()
