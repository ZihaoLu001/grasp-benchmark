param(
    [string]$Node = "em14",
    [ValidateSet("playground", "libero", "full")][string]$Mode = "full",
    [int]$Port = 6666,
    [int]$PlaygroundTrials = 1,
    [int]$LiberoTrialNum = 1,
    [int]$MaxTasksPerBenchmark = 1,
    [string]$Benchmarks = "libero_object,libero_10,libero_goal",
    [string]$ExpNamePrefix = "graspvla_official"
)

$args = @(
    "-m", "grasp_benchmark.official_graspvla_sim",
    "--node", $Node,
    "--mode", $Mode,
    "--port", $Port,
    "--playground-trials", $PlaygroundTrials,
    "--libero-trial-num", $LiberoTrialNum,
    "--max-tasks-per-benchmark", $MaxTasksPerBenchmark,
    "--benchmarks", $Benchmarks,
    "--exp-name-prefix", $ExpNamePrefix
)

python @args
