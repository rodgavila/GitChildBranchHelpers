from subcommands.arc_diff_against_parent import ArcDiffAgainstParent
from subcommands.arc_land_onto_parent import ArcLandOntoParent
from subcommands.base_command import BaseCommand as _BaseCommand
from subcommands.git_change_parent import GitChangeParent
from subcommands.git_make_child_branch import GitMakeChildBranch
from subcommands.git_rebase_children import GitRebaseOntoParent
from subcommands.git_remove_leaf_child import GitRemoveLeafBranch
from subcommands.git_rename_branch import GitRenameBranch
from subcommands.print_branch_info import PrintBranchInfo
from subcommands.print_child_branch_structure import PrintChildBranchStructure
from subcommands.set_branch_archived import SetBranchArchived

if False:
    from typing import Sequence, Set, Text

_ALL_COMMANDS = (
    ArcDiffAgainstParent(),
    ArcLandOntoParent(),
    GitChangeParent(),
    GitMakeChildBranch(),
    GitRebaseOntoParent(),
    GitRemoveLeafBranch(),
    GitRenameBranch(),
    PrintChildBranchStructure(),
    PrintBranchInfo(),
    SetBranchArchived(),
)


def get_commands():
    # type: () -> Sequence[_BaseCommand]
    seen_command_names = set()  # type: Set[Text]
    for subcommand in _ALL_COMMANDS:
        subcommand_name = subcommand.get_name()
        assert subcommand_name not in seen_command_names, "Duplicate command name: {}".format(subcommand_name)
        seen_command_names.add(subcommand_name)
    return sorted(_ALL_COMMANDS, key=lambda cmd: cmd.get_name())
