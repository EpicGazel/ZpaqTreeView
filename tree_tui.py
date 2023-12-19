"""
Code browser example.

Run with:

    python code_browser.py PATH
"""
import re
from sys import stderr, argv

from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.reactive import var
from textual.widgets import Tree, Footer, Header, Static, Input
from tqdm import tqdm
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
            if not tl_child_node.is_leaf():  # If directory, true
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
        ("escape", "exit_text_field", "Exit Text Field"),
        ("q", "quit", "Quit"),
    ] # TODO: f = find, x = extract, s = save, q = quit, i = file info, maybe something about file selection?

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
            # with VerticalScroll(id="code-view"):
            #     yield Static(id="code", expand=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Tree).focus()

    # def on_directory_tree_file_selected(
    #     self, event: Tree.FileSelected
    # ) -> None:
    #     """Called when the user click a file in the directory tree."""
    #     event.stop()
    #     # code_view = self.query_one("#code", Static)
    #     # try:
    #     #     syntax = Syntax.from_path(
    #     #         str(event.path),
    #     #         line_numbers=True,
    #     #         word_wrap=False,
    #     #         indent_guides=True,
    #     #         theme="github-dark",
    #     #     )
    #     # except Exception:
    #     #     code_view.update(Traceback(theme="github-dark", width=None))
    #     #     self.sub_title = "ERROR"
    #     # else:
    #     #     code_view.update(syntax)
    #     #     self.query_one("#code-view").scroll_home(animate=False)
        #     self.sub_title = str(event.path)

    def action_extract_menu(self) -> None:
        self.show_file_input = not self.show_file_input
        if self.show_file_input:
            self.query_one(Input).focus()
        else:
            self.current_node.tree.focus()

        self.query_one(Input).set_class(not self.show_file_input, "hidden")

    def action_exit_text_field(self) -> None:
        self.show_file_input = False
        self.query_one(Input).set_class(True, "hidden")
        self.query_one(Tree).focus()

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        self.current_node = event.node

    def on_input_submitted(self) -> None:
        input_box = self.query_one(Input)
        ztv.extract_file(config, input_file, self.current_node.data.fullPath, input_box.value,
                         len(self.current_node.children) > 0)
        input_box.value = ""
        self.action_extract_menu()


if __name__ == "__main__":
    config = ztv.load_create_config()
    input_file = "b:/g_drive.zpaq"
    tree = convert_filetree(config, input_file)
    TreeTUI().run()
