HTML_LIST_CUSTOM_TMPL = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <title>Test Summary Report</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 2em; background: #f9f9f9; }
            h1, h2 { color: #333; }
            .summary { background: #fff; padding: 1em; border-radius: 6px; margin-bottom: 2em; }
            table { width: 100%; border-collapse: collapse; background: #fff; }
            th, td { padding: 8px 10px; border: 1px solid #ccc; text-align: left; vertical-align: top; }
            th { background: #e9e9e9; }
            tr:nth-child(even) { background: #f5f5f5; }
            .true { color: green; font-weight: bold; }
            .false { color: #999; }
            ul { margin: 0; padding-left: 1em; }
        </style>
    </head>
    <body>
        <h1>🧪 Test Summary Report</h1>

        <div class="summary">
            <h2>Summary</h2>
            <ul>
                <li><strong>Total Files:</strong> {{ total_files }}</li>
                <li><strong>Total Test Classes:</strong> {{ total_classes }}</li>
                <li><strong>Total Test Methods:</strong> {{ total_tests }}</li>
                <li><strong>Unique Tags:</strong> {{ tags|length }} ({{ tags | join(', ') if tags else 'none' }})</li>
            </ul>
        </div>

        <h2>Detailed Overview</h2>
        <table>
            <thead>
                <tr>
                    <th>File Name</th>
                    <th>Class Name</th>
                    <th>Test Methods</th>
                    <th>SetupAll</th>
                    <th>Setup</th>
                    <th>Teardown</th>
                    <th>TeardownAll</th>
                </tr>
            </thead>
            <tbody>
                {% for f in files %}
                <tr>
                    <td title="{{ f.path }}">{{ f.filename }}</td>
                    <td>{{ f.classname }}</td>
                    <td>
                        <ul>
                        {% for test_name in f.test_names %}
                            <li>{{ test_name }}</li>
                        {% endfor %}
                        </ul>
                    </td>
                    <td class="{{ f.setup_all }}">{{ '✔' if f.setup_all else '—' }}</td>
                    <td class="{{ f.setup }}">{{ '✔' if f.setup else '—' }}</td>
                    <td class="{{ f.teardown }}">{{ '✔' if f.teardown else '—' }}</td>
                    <td class="{{ f.teardown_all }}">{{ '✔' if f.teardown_all else '—' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <footer style="margin-top: 2em; color: #777;">
            Generated dynamically — ready for CI/CD dashboards 🚀
        </footer>
    </body>
    </html>
    """

HTML_RESULT_CUSTOM_TMPL = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even){ background-color: #f9f9f9; }
        tr:hover { background-color: #f1f1f1; }
        .pass { background-color: #d4edda; }
        .fail { background-color: #f8d7da; }
        .error { background-color: #fff3cd; }
    </style>
</head>
<body>
    <h1>Automated Test Report</h1>

    <h2>Summary</h2>
    <ul>
        <li>Total tests: {{ total }}</li>
        <li>Passed: {{ passed }}</li>
        <li>Failed: {{ failed }}</li>
        <li>Errored: {{ errored }}</li>
    </ul>

    <h2>Details</h2>
    <table>
        <thead>
            <tr>
                <th>File</th>
                <th>Module</th>
                <th>Class</th>
                <th>Method</th>
                <th>Status</th>
                <th>Start Time</th>
                <th>End Time</th>
                <th>Elapsed (s)</th>
                <th>Exception</th>
                <th>Output</th>
            </tr>
        </thead>
        <tbody>
            {% for test in tests %}
            <tr class="{{ test.status }}">
                <td>{{ test.file_path }}</td>
                <td>{{ test.module_name }}</td>
                <td>{{ test.test_class_name or '' }}</td>
                <td>{{ test.test_method_name }}</td>
                <td>{{ test.status }}</td>
                <td>{{ test.start_time }}</td>
                <td>{{ test.end_time }}</td>
                <td>{{ '%.4f'|format(test.elapsed_seconds) }}</td>
                <td>
                    {% if test.exception_info %}
                        {{ test.exception_info[0] }}: {{ test.exception_info[1] }}
                    {% endif %}
                </td>
                <td>{{ test.output or '' }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <p>Generated on {{ generated_on }}</p>
</body>
</html>
"""
