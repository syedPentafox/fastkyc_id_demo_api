# I4C Request Status Workflow

```mermaid
flowchart LR
    N
    R
    P

    N --> R
    R --> P
```

```mermaid
flowchart LR
    invalid
    success
    failure
    start

    start --> invalid
    start --> success
    start --> failure
```