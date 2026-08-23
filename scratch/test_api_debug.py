import asyncio
import traceback
from backend.app.persistence.database import async_session_factory
from backend.app.persistence.repositories.workflow_repo import SqlWorkflowRepository
from backend.app.persistence.repositories.execution_repo import SqlExecutionRepository
from backend.app.services.workflow_service import WorkflowService
from backend.app.services.execution_service import ExecutionService

async def main():
    try:
        async with async_session_factory() as session:
            wf_repo = SqlWorkflowRepository(session)
            wf_service = WorkflowService(wf_repo)
            specs = await wf_service.list_workflows()
            print("Workflow specs loaded:", len(specs))
            for s in specs:
                print("Spec:", s.name, "Tasks:", len(s.tasks))

            exec_repo = SqlExecutionRepository(session)
            execs = await exec_repo.list_workflow_executions()
            print("Executions loaded:", len(execs))
    except Exception as e:
        print("EXCEPTION CAUGHT:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
