import logging
import time

from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine

load_dotenv()


class SqlProfiler:
    def __init__(self):
        """
        Enables ORM logs at the 'DEBUG' level, logging generated queries and their execution time.
        """
        self.enable_profiling = "ENABLE"  # os.getenv("ORM_QUERY_EXECUTION_LOGGING")
        if self.enable_profiling == "ENABLE":
            self._setup_logging()
            self._attach_event_listeners()

    def _setup_logging(self):
        logging.basicConfig()
        self.logger = logging.getLogger("myapp.sqltime")
        self.logger.setLevel(logging.DEBUG)

    def _attach_event_listeners(self):
        @event.listens_for(Engine, "before_cursor_execute")
        def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            conn.info.setdefault("query_start_time", []).append(time.time())
            formatted_statement = self._format_sql_statement(statement, parameters)
            self.logger.debug("SQL Statement: %s", formatted_statement)

        @event.listens_for(Engine, "after_cursor_execute")
        def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            total_time = time.time() - conn.info["query_start_time"].pop(-1)
            self.logger.debug("Total Time: %f", total_time)

    def _format_sql_statement(self, statement, parameters):
        if parameters:
            if isinstance(parameters, dict):
                return self._format_dict_parameters(statement, parameters)
            elif isinstance(parameters, tuple):
                return self._format_tuple_parameters(statement, parameters)
        return statement

    def _format_dict_parameters(self, statement, parameters):
        for key, value in parameters.items():
            if isinstance(value, str):
                statement = statement.replace(f"%({key})s", f"'{value}'")
            else:
                statement = statement.replace(f"%({key})s", str(value))
        return statement

    def _format_tuple_parameters(self, statement, parameters):
        values = ", ".join(str(tuple(values.values())) for values in parameters)
        return f"{statement.split('VALUES')[0]} VALUES {values}"
