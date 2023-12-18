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
from textual.widgets import Tree, Footer, Header, Static
from tqdm import tqdm
import zpaqtreeview as ztv


def convert_filetree(path):
    tl_tree = ztv.main()
    tx_tree = Tree(label=tl_tree.root, data=tl_tree.get_node(tl_tree.root).data)
    tl_node_stack = [tl_tree.get_node(tl_tree.root)]
    tx_stack = [tx_tree.root]

    print("Converting file tree to textual...")
    bar = tqdm(total=tl_tree.size(), unit="nodes", colour="green", leave=False)
    while len(tl_node_stack) > 0:
        tl_node = tl_node_stack.pop()
        tx_node = tx_stack.pop()

        # TODO: Sort children by directory first, then by name (A should be synonymous with a, lower()? etc)
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
        ("q", "quit", "Quit"),
    ] # TODO: f = find, x = extract, s = save, q = quit, i = file info, maybe something about file selection?

    show_tree = var(True)

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-tree")
        if show_tree:
            self.query_one(Tree).focus()

    def compose(self) -> ComposeResult:
        """Compose our UI."""
        path = "./" if len(argv) < 2 else argv[1]
        yield Header()
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

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree


if __name__ == "__main__":
    tree = convert_filetree("NOPATH")
    TreeTUI().run()
