from pathlib import Path

from pridexyz.color import RGBColor


class Builder:
    @classmethod
    def get_name(cls):
        raise NotImplementedError

    def __init__(
        self,
        logger,
        src: Path,
        build: Path,
        build_user: str,
        meta: dict,
        logger_base_indent: int = 1,
    ):
        self.logger = logger
        self.src_dir = src
        self.build_dir = build
        self.build_user = build_user
        self.meta = meta
        self.logger_base_indent = logger_base_indent

    def info(self, message: str, level: int = 2, **kwargs):
        self.logger.info(
            f"{'\t' * (level + self.logger_base_indent)}{message}", **kwargs
        )

    def debug(self, message: str, level: int = 2, **kwargs):
        self.logger.debug(
            f"{'\t' * (level + self.logger_base_indent)}{message}", **kwargs
        )

    def error(self, message: str, level: int = 2, **kwargs):
        self.logger.error(
            f"{'\t' * (level + self.logger_base_indent)}{message}", **kwargs
        )

    def build(self, palette: dict, palette_name: str, palette_colors: list[RGBColor]):
        raise NotImplementedError

    @classmethod
    def create_builders(cls, logger, src, build, build_user, meta, builder_class_list):
        builders = []
        for builder_class in builder_class_list:
            logger.info(
                f"Creating '{builder_class.__name__}' ({builder_class.get_name()})"
            )
            builders.append(
                builder_class(
                    logger, src / builder_class.get_name(), build, build_user, meta
                )
            )
        return builders
