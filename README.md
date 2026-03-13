# JSONPatch-Plus

This package extends the JSON Patch (RFC 6902) functionality with the following features:
- Preconditions for operations that prevent their execution
- Usage of JSONPaths over JSONPointers to allow operation targets with wildcards and conditions
- Change tracking of each operation (a list of additionas and deletions as JSONPointers)
- Listeners that can react to the tracked changes to dynamically perform customizable actions when something in the JSON document has changed

The JSONPath and JSONPatch implementations used as a basis are from https://pypi.org/project/python-jsonpath/

## Use Case
The functionalities in this package have been developed to serve the following use case:

A process P produces JSON objects.
Every time P executes the results needs to be adjusted with changes the user can configure.
So the set of operations is persisted and applied for every process run.
There are different processes and each requires a different set of user operations.
Additionally, the produced JSON objects can have patterns that can be changed automatically instead of with a manual user action.
However, the automated steps might be dependent on the order of user operations.
So instead of appending or prepending the automated operations, a listener approach is used to apply the automated operation as soon as a certain path in the document is modified (triggered).
For this to work properly the first operation is always an AddOperation that 
adds the entire existing object therefore the tracking produces an addition for every JSONPointer in the document.

