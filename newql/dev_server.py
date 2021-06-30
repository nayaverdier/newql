import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import import_module

from newql import Schema

GRAPHIQL = """
<html>
    <head>
        <meta charset="UTF-8">
        <title>NewQL Dev Server (GraphiQL)</title>
        <link href="https://unpkg.com/graphiql/graphiql.min.css" rel="stylesheet" />
    </head>
    <body style="margin: 0;">
        <div id="graphiql" style="height: 100vh;"></div>
        <script crossorigin src="https://unpkg.com/react/umd/react.production.min.js"></script>
        <script crossorigin src="https://unpkg.com/react-dom/umd/react-dom.production.min.js"></script>
        <script crossorigin src="https://unpkg.com/graphiql/graphiql.min.js"></script>
        <script>
         const fetcher = graphQLParams =>
             fetch('/', {
                 method: 'post',
                 headers: {'Content-Type': 'application/json'},
                 body: JSON.stringify(graphQLParams),
             }).then(response => response.json()).catch(() => response.text());

         ReactDOM.render(React.createElement(GraphiQL, {fetcher}), document.getElementById('graphiql'));
        </script>
    </body>
</html>
"""


def run(schema: Schema, address: str, port: int):
    class Handler(BaseHTTPRequestHandler):
        def _set_headers(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

        def do_GET(self):
            self._set_headers()
            self.wfile.write(GRAPHIQL.encode("utf-8"))

        def do_POST(self):
            self._set_headers()
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            result = schema.execute(request["query"], request.get("variable"), request.get("operation"))
            self.wfile.write(json.dumps(result).encode("utf-8"))

    print(f"Starting NewQL Dev Server at {address}:{port}")
    HTTPServer((address, port), Handler).serve_forever()


def _import_schema(import_path: str) -> Schema:
    module_path, schema = import_path.rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, schema)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a simple HTTP server")
    parser.add_argument(
        "-l",
        "--listen",
        default="localhost",
        help="Specify the IP address on which the server listens",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8000,
        help="Specify the port on which the server listens",
    )
    parser.add_argument(
        "-s",
        "--schema",
        type=str,
        default="newql.example.user_schema",
        help="The full import name of the schema to server",
    )
    args = parser.parse_args()
    schema = _import_schema(args.schema)
    run(schema, args.listen, args.port)
