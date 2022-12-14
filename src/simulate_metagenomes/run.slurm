#!/bin/bash

### REQUIRED: 
### Research group/PI
#SBATCH --account=bhurwitz
### Job queue (standard|windfall|high_pri)
### If windfall, omit --account
#SBATCH --partition=standard
### Number of nodes
#SBATCH --nodes=1
### Number of CPUs per node 
#SBATCH --ntasks=1
### Amount of memory per node
#SBATCH --mem-per-cpu=5gb
### Job walltime (HHH:MM:SS)
#SBATCH --time=7-00:00:00
### OPTIONAL:
### Job name
### SBATCH --job-name=JobName
### Standard output filename
### SBATCH -o out_filename.txt
### Standard error filename
### SBATCH -e error_filename.txt
### Email notifications (BEGIN|END|FAIL|ALL)
### SBATCH --mail-type=ALL
### Email addresss
### SBATCH --mail-user=schackartk@email.arizona.edu

# Activate a conda environment
source activate ../../env

# Run snakemake cluster
snakemake \
	--cluster-config config/cluster.yaml \
	-j 12 \
	--latency-wait 60 \
	--configfile config/config.yaml \
	--cluster \
		"sbatch -p {cluster.partition} \
		--account {cluster.group} \
		-t {cluster.time} \
		--mem-per-cpu={cluster.mem-per-cpu} \
		--nodes=1 \
		--ntasks={cluster.ntasks} \
		-e {cluster.e} \
		-o {cluster.o}"

