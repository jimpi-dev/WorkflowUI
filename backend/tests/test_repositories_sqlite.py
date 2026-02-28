import pytest

from db.init import init_db
from repositories.sqlite import SqliteWorkflowRepository
from domain.workflow import WorkflowDefinition, WorkflowVersion


@pytest.fixture
def temp_db_path(tmp_path):
    db_file = tmp_path / "test_workflow.db"
    init_db(str(db_file))
    return str(db_file)


@pytest.fixture
def workflow_repo(temp_db_path):
    return SqliteWorkflowRepository(temp_db_path)


def test_create_and_get_workflow_definition(workflow_repo):
    w = workflow_repo.create_workflow_definition("wf-1", "TestWorkflow", 1000)
    assert w.id == "wf-1"
    assert w.name == "TestWorkflow"
    assert w.created_at == 1000

    found = workflow_repo.get_workflow_by_name("TestWorkflow")
    assert found is not None
    assert found.id == "wf-1"


def test_get_latest_version_none_for_new_workflow(workflow_repo):
    workflow_repo.create_workflow_definition("wf-1", "A", 1000)
    assert workflow_repo.get_latest_version("wf-1") is None


def test_create_version_and_get_latest(workflow_repo):
    workflow_repo.create_workflow_definition("wf-1", "A", 1000)
    v1 = workflow_repo.create_workflow_version(
        "ver-1", "wf-1", 1, "hash1", "{}", "[]", "[]", 1001
    )
    assert v1.version == 1

    latest = workflow_repo.get_latest_version("wf-1")
    assert latest is not None
    assert latest.id == "ver-1"
    assert latest.graph_hash == "hash1"

    v2 = workflow_repo.create_workflow_version(
        "ver-2", "wf-1", 2, "hash2", "{}", "[]", "[]", 1002
    )
    latest2 = workflow_repo.get_latest_version("wf-1")
    assert latest2.version == 2
    assert latest2.graph_hash == "hash2"


def test_run_in_transaction_commit(workflow_repo):
    def do_create(conn):
        workflow_repo.create_workflow_definition("wf-tx", "TxWorkflow", 2000, conn=conn)
        workflow_repo.create_workflow_version(
            "ver-tx", "wf-tx", 1, "h", "{}", "[]", "[]", 2001, conn=conn
        )

    workflow_repo.run_in_transaction(do_create)

    w = workflow_repo.get_workflow_by_name("TxWorkflow")
    assert w is not None
    v = workflow_repo.get_latest_version("wf-tx")
    assert v is not None
