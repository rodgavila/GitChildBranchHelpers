from collections import defaultdict
import csv
import os
import subprocess
import shutil

try:
    # noinspection PyUnresolvedReferences
    from typing import (
        Any,
        Callable,
        Dict,
        Iterable,
        List,
        Tuple,
        TypeVar,
        Union,
    )
except ImportError:
    pass

def git(command):
    # type: (str) -> str
    return run_command_expecting_failure(subprocess.check_output, "git", command)


def get_current_branch():
    # type: () -> str
    return git("rev-parse --abbrev-ref HEAD").strip()


def get_branch_tracker():
    # type: () -> BranchTrackerWrapper
    git_dir = git("rev-parse --git-dir").strip()
    config_dir = os.path.join(git_dir, "child_branch_helper")
    if os.path.exists(config_dir):
        assert os.path.isdir(config_dir)
    else:
        os.mkdir(config_dir)
    config_file = os.path.join(config_dir, "branches.csv")
    # Make sure the config file exists
    if not os.path.exists(config_file):
        open(config_file, "a").close()
    return BranchTrackerWrapper(config_file)


def does_branch_contain_commit(branch, commit):
    # type: (str, str) -> bool
    return git("branch --contains %s" % commit).find(" %s\n" % branch) >= 0


def fail_if_not_rebased(current_branch, parent, tracker):
    # type: (str, str, BranchTracker) -> None
    bases = tracker.bases_for_branch(current_branch)
    assert len(bases) in (1, 2)
    if len(bases) == 2 or not does_branch_contain_commit(parent, bases[0]):
        print "Please rebase this branch on top of its parent"
        exit()


def arc(command):
    # type: (str) -> None
    run_command_expecting_failure(subprocess.check_call, "arc", command)

T = TypeVar('T')


def run_command_expecting_failure(command_runner, program, command):
    # type: (Callable[[List[str]], T], str, str) -> T
    try:
        return command_runner([program] + command.split(" "))
    except subprocess.CalledProcessError:
        print ""
        print "!!!!!!!!"
        print "!!! Failed to run/finish %s command:" % program
        print "!!! `%s %s`" % (program, command)
        print "!!!!!!!!"
        print ""
        exit(1)
    except KeyboardInterrupt:
        print ""
        print "User aborted command: `%s %s`" % (program, command)
        print ""
        exit(1)


class BranchTrackerWrapper(object):
    def __init__(self, config_file):
        # type: (str) -> None
        super(BranchTrackerWrapper, self).__init__()
        self.config_file = config_file

    def __enter__(self):
        # type: () -> BranchTracker
        self.branch_tracker = BranchTracker(self.config_file)
        return self.branch_tracker

    def __exit__(self, exc_type, exc_value, exc_traceback):
        # type: (Any, Any, Any) -> None
        self.branch_tracker.save_to_file()


class BranchTracker(object):
    def __init__(self, config_file):
        # type: (str) -> None
        super(BranchTracker, self).__init__()
        self._config_file = config_file
        self._child_to_parent = {}  # type: Dict[str, str]
        self._parent_to_children = defaultdict(list)  # type: Dict[str, List[str]]
        self._branch_to_bases = {}  # type: Dict[str, Tuple[str,...]]
        # Read config file
        with open(config_file, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                child, parent, base, rebase_base = row
                assert child not in self._child_to_parent
                assert child not in self._branch_to_bases
                self._child_to_parent[child] = parent
                self._parent_to_children[parent].append(child)
                assert base
                if rebase_base:
                    self._branch_to_bases[child] = (base, rebase_base)
                else:
                    self._branch_to_bases[child] = (base, )

    def save_to_file(self):
        # type: () -> None
        tmp_config_file = self._config_file + ".tmp"
        with open(tmp_config_file, "w") as f:
            writer = csv.writer(f)
            for child, parent in self._child_to_parent.items():
                bases = self._branch_to_bases[child]
                if len(bases) == 1:
                    base = bases[0]
                    rebase_base = ""
                else:
                    base, rebase_base = bases
                writer.writerow([child, parent, base, rebase_base])
        shutil.move(tmp_config_file, self._config_file)

    def parent_for_child(self, child):
        # type: (str) -> str
        return self._child_to_parent[child]

    def children_for_parent(self, parent):
        # type: (str) -> List[str]
        return self._parent_to_children[parent]

    def bases_for_branch(self, branch):
        # type: (str) -> Tuple[str,...]
        return self._branch_to_bases[branch]

    def get_all_parents(self):
        # type: () -> Iterable[str]
        return self._parent_to_children.keys()

    def has_parent(self, branch):
        # type: (str) -> bool
        return branch in self._child_to_parent

    def collapse_and_remove_parent(self, old_parent):
        # type: (str) -> None
        # Remove the old parent from its parent, use that as the new parent
        new_parent = self._child_to_parent.pop(old_parent)
        self._parent_to_children[new_parent].remove(old_parent)

        # Remove the old parent's base branches
        self._branch_to_bases.pop(old_parent)

        # Update the old parent's children to point to the new parent
        if old_parent in self._parent_to_children:
            children = self._parent_to_children.pop(old_parent)
            self._parent_to_children[new_parent].extend(children)
            for child in children:
                self._child_to_parent[child] = new_parent

    def add_child_for_parent(self, parent, new_child, child_base):
        # type: (str, str, str) -> None
        self._child_to_parent[new_child] = parent
        self._parent_to_children[parent].append(new_child)
        self._branch_to_bases[new_child] = (child_base, )

    def start_rebase(self, branch, new_base):
        # type: (str, str) -> None
        bases = self._branch_to_bases[branch]
        assert len(bases) == 1
        self._branch_to_bases[branch] = bases + (new_base, )

    def finish_rebase(self, branch, new_base):
        # type: (str, str) -> None
        bases = self._branch_to_bases[branch]
        assert len(bases) == 2
        self._branch_to_bases[branch] = (new_base, )

    def rename_branch(self, old_branch, new_branch):
        # type: (str, str) -> None
        self._branch_to_bases[new_branch] = self._branch_to_bases.pop(old_branch)

        if old_branch in self._child_to_parent:
            parent = self._child_to_parent[new_branch] = self._child_to_parent.pop(old_branch)
            self._parent_to_children[parent].remove(old_branch)
            self._parent_to_children[parent].append(new_branch)

        if old_branch in self._parent_to_children:
            children = self._parent_to_children[new_branch] = self._parent_to_children.pop(old_branch)
            for child in children:
                self._child_to_parent[child] = new_branch

    def remove_child_leaf(self, child_leaf):
        # type: (str) -> None
        children = self._parent_to_children[child_leaf]
        assert not children, "Expected branch to be a leaf node, had %s child(ren)." % len(children)

        if child_leaf in self._child_to_parent:
            parent = self._child_to_parent.pop(child_leaf)
            self._parent_to_children[parent].remove(child_leaf)

    def set_parent(self, child, new_parent):
        # type: (str, str) -> None
        if child in self._child_to_parent:
            old_parent = self._child_to_parent[child]
            self._parent_to_children[old_parent].remove(child)

        self._child_to_parent[child] = new_parent
        self._parent_to_children[new_parent].append(child)


def hash_for(rev):
    # type: (str) -> str
    return git("rev-parse --verify %s" % rev).strip()
