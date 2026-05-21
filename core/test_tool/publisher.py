import logging
from datetime import datetime
from typing import Any

from libs.sql_ops.querybuilder.querybuilder import QueryBuilder
from libs.sql_ops.table_ops import verify_table_presence
from libs.test_ops.test_info import DatabaseRecord, TestInfo, TestMethodInfo
from libs.test_ops.utils import _get_username, get_db_conn
from libs.utils.git_utils import get_branches_with_file, get_git_path_with_repo_folder

logger = logging.getLogger(__name__)


def publish_to_test_warehouse(test_data: TestInfo, config: dict = {}):
    """
    Publishes test cases to the test warehouse database.

    Args:
        test_data (TestInfo): A dictionary where the keys are file paths and the values are TestInfo objects.
        config (dict): A dictionary containing configuration for the test warehouse database.

    Returns:
        tuple[int, int, int]: A tuple containing the number of test cases published, updated, and skipped.

    Raises:
        Exception: If there is an error while processing the test data.
    """
    if not config:
        logger.error("Unable to upload test cases: No config provided")
        return

    published_count = 0
    updated_count = 0
    skipped_count = 0
    try:
        for _, test_info in test_data.items():
            for test in test_info.test_methods:
                result = _process_test_case(test_info, test, config)
                if result == "published":
                    published_count += 1
                elif result == "updated":
                    updated_count += 1
                elif result == "skipped":
                    skipped_count += 1

    except Exception as e:
        logger.error(f"Failed to process test data: {e}")

    return published_count, updated_count, skipped_count


def _process_test_case(test_data: TestInfo, test: TestMethodInfo, config: dict):
    """
    Process a test case and publish it to the test warehouse database.

    Args:
        test_data (TestInfo): A dictionary where the keys are file paths and the values are TestInfo objects.
        test (TestMethodInfo): A TestMethodInfo object containing information about a test case.
        config (dict): A dictionary containing configuration for the test warehouse database.

    Returns:
        str: A string indicating whether the test case was published, updated, or skipped.

    Raises:
        Exception: If there is an error while processing the test data.
    """
    conn_str = get_db_conn(config)
    qb = QueryBuilder(
        schema="holistiq_testops", table_name="testcases", db_conn=conn_str
    )
    verify_table_presence(db_conn=conn_str, table_name="testcases")
    # Prepare test case data
    data = _prepare_test_case_data(test_data, test)

    # Check for existing record
    existing_records = _get_existing_record(qb, data["contenthash"])

    if existing_records:
        return _handle_existing_record(qb, data, existing_records[0])
    else:
        return _publish_new_record(qb, data)


def _prepare_test_case_data(
    test_case: TestInfo, test: TestMethodInfo
) -> dict[str, Any]:
    """
    Prepares a dictionary of test case data from a given test case and test method.

    Args:
        test_case (TestInfo): A TestInfo object containing information about a test case.
        test (TestMethodInfo): A TestMethodInfo object containing information about a test method.

    Returns:
        dict[str, Any]: A dictionary containing the test case data.

    """

    branches = get_branches_with_file(test_case.file_path)

    return {
        "branch": "; ".join(branches),
        "filepath": get_git_path_with_repo_folder(test_case.file_path),
        "module": test_case.module_name,
        "class": test_case.name,
        "test_case": test.name,
        "setup": True if test_case.setup_test_method else False,
        "setupall": True if test_case.setup_all_method else False,
        "teardown": True if test_case.teardown_test_method else False,
        "teardownall": True if test_case.teardown_all_method else False,
        "contenthash": test.hashkey,
    }


def _get_existing_record(qb: QueryBuilder, hash_support: str) -> list[dict[str, Any]]:
    """
    Queries the test case results table for an existing record with a given hash support.

    Args:
        qb (QueryBuilder): A QueryBuilder object for constructing and executing SQL queries.
        hash_support (str): The hash support for the test case.

    Returns:
        list[dict[str, Any]]: A list of dictionaries containing the existing record's branch and content hash.
    """
    try:
        result = (
            qb.select("branch, contenthash")
            .where("contenthash", "=", hash_support)  # type: ignore
            .execute()
        )
        qb.reset()
        return result or []
    except Exception:
        logger.exception("Failed to query existing record")
        return []


def _handle_existing_record(
    qb: QueryBuilder, data: dict[str, Any], existing: dict[str, Any]
) -> str:
    """
    Handles an existing record in the test case results table.

    If the branch has changed, calls `_update_branches` to update the record.
    Otherwise, logs a debug message indicating no changes were detected and returns "skipped".
    """

    existing_record = DatabaseRecord(
        branch=existing.get("branch"), hashkey=existing.get("contenthash")
    )
    # Check if branches changed
    if existing_record.branch and data["branch"] != existing_record.branch:
        return _update_branches(qb, data, existing_record.hashkey)
    logger.debug(f"No changes detected for {data['test_case']}")
    return "skipped"


def _publish_new_record(qb: QueryBuilder, data: dict[str, Any]) -> str:
    """
    Publish a new test case to the test warehouse database.

    Args:
        qb (QueryBuilder): A QueryBuilder object for constructing and executing SQL queries.
        data (dict[str, Any]): A dictionary containing the test case data to be published.

    Returns:
        str: A string indicating whether the test case was published or skipped.

    Raises:
        Exception: If there is an error while publishing the test case.
    """
    try:
        publish_data = {"published_by": _get_username()}
        final_data = {**data, **publish_data}
        qb.insert(final_data).execute()
        logger.info(f"Published new test case: {data['test_case']}")
        return "published"

    except Exception as e:
        logger.error(f"Failed to publish {data['test_case']}: {e}")
        return "skipped"


def _update_branches(qb: QueryBuilder, data: dict[str, Any], hashkey: str) -> str:
    """
    Updates the branches for a test case in the test warehouse database.

    Args:
        qb (QueryBuilder): A QueryBuilder object for constructing and executing SQL queries.
        data (dict[str, Any]): A dictionary containing the test case data to be updated.
        hashkey (str): The hash key of the test case to be updated.

    Returns:
        str: A string indicating whether the branches were updated or skipped.

    Raises:
        Exception: If there is an error while updating the branches.
    """
    update_data = {
        "update_date": datetime.now(),
        "updated_by": _get_username(),
        "branch": data["branch"],
    }
    try:
        qb.update(update_data).where("contenthash", "=", hashkey).execute()
        logger.info(f"Updated branches for {data['testcase']}")
        return "updated"

    except Exception as e:
        logger.error(f"Failed to update branches for {data['testcase']}: {e}")
        return "skipped"
