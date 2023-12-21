"""
Code browser example.

Run with:

    python code_browser.py PATH
"""
from sys import argv
from os import getcwd
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import var
from textual.widgets import Tree, Footer, Header, Input
from tqdm import tqdm
from tkinter import filedialog
import zpaqtreeview as ztv


def convert_filetree(config=None, file_path=None):
    tl_tree = ztv.main(config, file_path)
    tx_tree = Tree(label=tl_tree.root, data=tl_tree.get_node(tl_tree.root).data)
    tl_node_stack = [tl_tree.get_node(tl_tree.root)]
    tx_stack = [tx_tree.root]

    print("Converting file tree to textual...")
    bar = tqdm(total=tl_tree.size(), unit="nodes", colour="green", leave=False)
    while len(tl_node_stack) > 0:
        tl_node = tl_node_stack.pop()
        tx_node = tx_stack.pop()

        children_sorted = tl_tree.children(tl_node.tag)
        children_sorted.sort(key=lambda x: (x.is_leaf(), x.data.name.lower()))
        for tl_child_node in children_sorted:
            if tl_child_node.data.is_directory():  # not tl_child_node.is_leaf():  # If directory, true
                tl_node_stack.append(tl_child_node)
                tx_stack.append(
                    tx_node.add(tl_child_node.data.name, data=tl_child_node.data))
            else:
                tx_node.add_leaf(tl_child_node.data.name, data=tl_child_node.data)

            bar.update()

    bar.close()
    return tx_tree


class TreeTUI(App):
    """Tree view of zpaqfranz archive."""

    CSS_PATH = "tree_tui.tcss"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("x", "extract_menu", "Extract"),
        ("q", "quit", "Quit"),
    ]  # TODO: f = find, x = extract, s = save, q = quit, i = file info, maybe something about file selection?

    show_tree = var(True)
    show_file_input = var(False)
    current_node = var(None)

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-tree")
        if show_tree:
            self.query_one(Tree).focus()

    def watch_show_file_input(self, show_file_input: bool) -> None:
        """Called when show_file_input is modified."""
        if show_file_input:
            self.query_one(Input).focus()

    def compose(self) -> ComposeResult:
        """Compose our UI."""
        path = "./" if len(argv) < 2 else argv[1]
        yield Header()
        yield Input(id="file-input", classes="hidden")
        with Container():
            yield tree
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()


    def action_extract_menu(self) -> None:
        out_directory = filedialog.askdirectory(initialdir=getcwd(), mustexist=True, title="Select output directory")
        ztv.extract_file(config, input_file, self.current_node.data.fullPath, out_directory, self.current_node.data.is_directory())
        # TODO: Toast notification of extraction result

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        self.current_node = event.node


if __name__ == "__main__":
    config = ztv.load_create_config()
    if len(argv) == 1:
        input_file = None
        while input_file is None:
            input_file = filedialog.askopenfilename(initialdir=getcwd(), title="Select a zpaq file",)
    elif len(argv) == 2:
        input_file = argv[1]
    else:
        print("Too many arguments.", file=stderr)
        exit(1)
    tree = convert_filetree(config, input_file)
    TreeTUI().run()
