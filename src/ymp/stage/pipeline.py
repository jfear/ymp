"""Pipelines Module

Contains classes for pre-configured pipelines comprising multiple
stages.
"""

import logging

from ymp.stage import StageStack
from ymp.stage.base import ConfigStage
from ymp.exceptions import YmpConfigError


log = logging.getLogger(__name__)  # pylint: disable=invalid-name


class Pipeline(ConfigStage):
    """
    Represents a subworkflow or pipeline
    """
    def __init__(self, name, cfg):
        super().__init__(name, cfg)
        self.stages = cfg
        self.stagestack = StageStack.get(".".join(self.stages))

        self.output_map = {}
        stage_names = list(self.stages)
        while stage_names:
            path = ".".join(stage_names)
            stage = self.stagestack._find_stage(stage_names.pop())
            if not stage:
                continue
            for fname in stage.outputs:
                if fname not in self.output_map:
                    self.output_map[fname] = path

    @property
    def project(self):
        """

        """
        import ymp
        cfg = ymp.get_config()
        if self.stages[0] in cfg.projects:
            return cfg.projects[self.stages[0]]
        if self.stages[0] in cfg.pipelines:
            return cfg.pipelines[self.stages[0]].project
        raise YmpConfigError(self.stages, "Pipeline must start with project")

    def get_path(self, suffix=None):
        return self.name

    @property
    def outputs(self):
        return list(self.output_map.keys())

    @property
    def stamp(self):
        return self.dir + "/all_targets.stamp"
