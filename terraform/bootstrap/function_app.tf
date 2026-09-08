import azure.functions as func
import logging

app = func.FunctionApp()


@app.function_name(name="process_request")
@app.queue_trigger(
    arg_name="msg",
    queue_name="infrastructure-requests",
    connection="AzureWebJobsStorage"
)
def process_request(msg: str) -> None:
    logging.info("========== PROCESS_REQUEST START ==========")
    logging.info("MESSAGE RECEIVED: %s", msg)
    logging.info("========== PROCESS_REQUEST END ==========")