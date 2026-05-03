from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import multiprocessing.queues


log = logging.getLogger(__name__)




def create_app(result_queue:  multiprocessing.queues.Queue,
               control_queue: multiprocessing.queues.Queue,
               status_queue:  multiprocessing.queues.Queue,
               command_queue: multiprocessing.queues.Queue
               ) -> FastAPI:
    
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):

        log.info("API Starting..")

        app.state.result_queue = result_queue
        app.state.control_queue = control_queue
        app.state.status_queue = status_queue
        app.state.command_queue = command_queue

        app.state.system_status = {
            "CameraProcess": {
                "status": "UNKNOWN",
                "message": "Waiting for status..."
            },
            "DetectorProcess": {
                "status": "UNKNOWN",
                "message": "Waiting for status..."
            },
        }

        yield

        log.info("FastAPI shutting down")

        log.info("API shutdown complete")

    app = FastAPI(
        title="Parking Management System",
        description="API for automated parking management",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",      # Swagger UI
        redoc_url="/redoc",     # ReDoc UI
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    return app
