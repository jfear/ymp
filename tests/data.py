from ymp.common import odict
from collections import OrderedDict

import pytest

data_types = ['any', 'metagenome', 'amplicon']

dataset_map = {
    'any': ['toy', 'mpic'],
    'metagenome': ['toy'],
    'large': ['ibd'],
    'amplicon': ['mpic']
}

target_map = {
    'any': odict[
        # fastq.rules
        'import':         '{}/all',
        'correct_bbmap':  '{}.correct_bbmap/all',
        'trim_bbmap':     '{}.trim_bbmapAQ10/all',
        'filter_bbmap':   '{}.ref_phiX.remove_bbmap/all',
        'dedup_bbmap':    '{}.dedup_bbmap/all',
        # fails due to bugs in phyloFlash with too few organisms
        #'phyloFlash':     'reports/{}.phyloFlash.pdf',
        'fastqc':         '{}.qc_fastqc/all',
        'multiqc':        'reports/{}.fastqc.html',
        'trimmomaticT32': '{}.trimmomaticT32/all',
        'sickle':         '{}.sickle/all',
        'sickleQ10':      '{}.sickleQ10/all',
        'sickleL10':      '{}.sickleL10/all',
        'sickleQ10L10':   '{}.sickleQ10L10/all',
    ],
    'metagenome': odict[
        # can't run bmtagger with less than 9GB RAM
        # 'bmtagger':       '{}.bmtaggerRMphiX/all',
        # assembly.rules
        'assemble_separate_mh': '{}.by_ID.assemble_megahit/all',
        'assemble_grouped_mh':  '{}.by_Subject.assemble_megahit/all',
        'assemble_joined_mh':   '{}.assemble_megahit/all',
        'assemble_separate_sp': '{}.by_ID.sp/all',
        'assemble_grouped_sp':  '{}.by_Subject.sp/all',
        'assemble_joined_sp':   '{}.sp/all',
        'metaquast_mh':         'reports/{}.assemble_megahit.mq.html',
        'metaquast_sp':         'reports/{}.sp.mq.html',
        # mapping.rules
        'map_bbmap_separate':   '{}.by_ID.assemble_megahit.map_bbmap/all',
        'map_bbmap_grouped':   '{}.by_Subject.assemble_megahit.map_bbmap/all',
        'map_bbmap_joined':   '{}.assemble_megahit.map_bbmap/all',
        'map_bowtie2_separate': '{}.by_ID.assemble_megahit.map_bowtie2/all',
        'map_bowtie2_grouped': '{}.by_Subject.assemble_megahit.map_bowtie2/all',
        'map_bowtie2_joined': '{}.assemble_megahit.map_bowtie2/all',
        # mapping vs reference
        'map_bbmap_reference': '{}.ref_genome.map_bbmap/all',
        'map_bowtie2_reference': '{}.ref_genome.map_bowtie2/all',
    ],
    'amplicon': odict[
        'bbduk_primer': '{}.primermatch/all'
    ]
}


targets = OrderedDict()
for target_type in target_map:
    targets.update(target_map[target_type])


def get_targets(large=True, exclude_targets=[]):
    target_dir_pairs = (
        pytest.param(dataset, target_map[dtype][target], dataset,
                     id="-".join((dataset, target)))
        for dtype in data_types
        for dataset in dataset_map[dtype]
        for target in target_map[dtype]
        if large or dataset not in dataset_map['large']
        if target not in exclude_targets
    )
    return target_dir_pairs

def parametrize_target(large=True, exclude_targets=[]):
    return pytest.mark.parametrize(
        "project_dir,target,project",
        get_targets(large, exclude_targets),
        indirect=['project_dir','target'])


    # blast.rules
    #'blast_gene_find':   '{}.by_Subject.mhc.blast/query.q1.csv',
    # coverage rules
    #'coverage_bbm': '{}.by_Subject.mhc.bbm.cov/blast.query.q1.csv',
    #'coverage_bt2': '{}.by_Subject.mhc.bt2.cov/blast.query.q1.csv'
    # otu.rules
    # 'otu_table':         '{}.by_Subject.mhc.blast.otu/psa.wcfR.otu_table.csv'

