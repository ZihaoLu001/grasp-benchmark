param(
    [string]$Input = "artifacts\\runs"
)

python -m grasp_benchmark.report.aggregate --input $Input
