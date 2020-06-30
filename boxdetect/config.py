import yaml


class PipelinesConfig:
    def __init__(self, yaml_path=None):
        """  # NOQA E501
        Helper class to keep all the important config variables in a single place.
        Use `save_` / `load_` functions to store configs in files and load when necessary.

        Args:
            yaml_path (str, optional): 
                If provided it will try to first load default values for the config and
                then load a saved configuration from a `yaml` file. Defaults to None.
        """
        # Important to adjust these values to match the size of boxes on your image  # NOQA E501
        self.width_range = [(40, 50)]
        self.height_range = [(50, 60)]

        # w/h ratio range for boxes/rectangles filtering
        self.wh_ratio_range = [(0.65, 0.1)]

        # The more scaling factors the more accurate the results
        # but also it takes more time to processing.
        # Too small scaling factor may cause false positives
        # Too big scaling factor will take a lot of processing time
        self.scaling_factors = [0.5]

        # Drawing rectangles
        self.thickness = 2

        # Image processing
        self.dilation_kernel = [(2, 2)]
        # Num of iterations when running dilation tranformation (to engance the image)  # NOQA E501
        self.dilation_iterations = [0]

        self.morph_kernels_type = ['lines']  # 'rectangles'
        self.morph_kernels_thickness = [1]

        # Rectangles grouping
        self.group_size_range = (1, 100)  # minimum number of rectangles in a group, >2 - will ignore groups with single rect  # NOQA E501
        self.vertical_max_distance = [10]  # in pixels
        self.horizontal_max_distance = [self.width_range[0][0] * 2]

        if yaml_path:
            self.load_yaml(yaml_path)

        self.update_num_iterations()

    def update_num_iterations(self):
        self.num_iterations = 1
        for variable in [
            self.width_range, self.height_range, self.wh_ratio_range,
            self.dilation_kernel,
            self.dilation_iterations, self.morph_kernels_type,
            self.horizontal_max_distance,
            self.morph_kernels_thickness, self.vertical_max_distance
        ]:
            if type(variable) is not list:
                variable = [variable]
            self.num_iterations = len(variable) if self.num_iterations < len(variable) else self.num_iterations  # NOQA E501

    def __conv_to_list(self, x, max_items):
        if type(x) is list:
            if len(x) >= max_items:
                return x
            x = x[0]
        return [x for i in range(max_items)]

    def variables_as_iterators(self):
        self.update_num_iterations()

        variables_list = [
            self.width_range, self.height_range, self.wh_ratio_range,
            self.dilation_iterations,
            self.dilation_kernel, self.vertical_max_distance,
            self.horizontal_max_distance,
            self.morph_kernels_type,
            self.morph_kernels_thickness
        ]
        return zip(
            *[self.__conv_to_list(variable, self.num_iterations)
                for variable in variables_list])

    def __add_margin_to_size(
            self, size, margin_percent=0.1, margin_px_limit=5):
        calc_margin = int((size * margin_percent))
        return calc_margin if calc_margin < margin_px_limit else margin_px_limit  # NOQA E501

    def autoconfigure(
            self, box_sizes, epsilon=5,
            margin_percent=0.1, margin_px_limit=5,
            use_rect_kernel_for_small=False, rect_kernel_threshold=30):
        from sklearn import cluster
        import numpy as np

        dbscan = cluster.DBSCAN(eps=epsilon, min_samples=1)
        clusters = dbscan.fit_predict(box_sizes)
        box_sizes = np.asarray(box_sizes)

        hw_grouped = []

        for i in range(0, max(clusters)+1):
            group = box_sizes[clusters == i]

            minh, maxh = (min(group[:, 0]), max(group[:, 0]))
            minw, maxw = (min(group[:, 1]), max(group[:, 1]))

            calc_minh = minh - self.__add_margin_to_size(
                minh, margin_percent, margin_px_limit)
            calc_maxh = maxh + self.__add_margin_to_size(
                maxh, margin_percent, margin_px_limit)
            calc_minw = minw - self.__add_margin_to_size(
                minw, margin_percent, margin_px_limit)
            calc_maxw = maxw + self.__add_margin_to_size(
                maxw, margin_percent, margin_px_limit)

            hw_grouped.append([
                (calc_minh, calc_maxh), (calc_minw, calc_maxw),
                sorted((calc_minw / calc_minh, calc_maxw / calc_maxh)),
                'rectangles' if (
                    use_rect_kernel_for_small
                    and maxh <= rect_kernel_threshold
                    and maxw <= rect_kernel_threshold)
                else 'lines'
            ])
        hw_grouped = np.asarray(hw_grouped)

        self.width_range = hw_grouped[:, 1].tolist()
        self.height_range = hw_grouped[:, 0].tolist()
        self.wh_ratio_range = hw_grouped[:, 2].tolist()
        self.morph_kernels_type = hw_grouped[:, 3].tolist()

        self.update_num_iterations()

        return self

    def save_yaml(self, path):
        """
        Saves current config into `yaml` file based on provided `path`.

        Args:
            path (str):
                Path to the file to save config.
        """
        variables_dict = {
            key: value
            for key, value in self.__dict__.items()
            if not key.startswith('__') and not callable(key)
        }
        with open(r'%s' % path, 'w') as file:
            yaml.dump(variables_dict, file)

    def load_yaml(self, path, suppress_warnings=False):
        """
        Loads configuration from `yaml` file based on provided `path`.

        Args:
            path (str):
                Path to the file to load config from.
            suppress_warnings (bool, optional):
                To show or not show warnings about potential mismatches.
                Defaults to False.
        """
        with open(r'%s' % path, 'r') as file:
            variables_dict = yaml.load(file, Loader=yaml.FullLoader)

        for key, value in variables_dict.items():
            if not suppress_warnings and key not in self.__dict__.keys():
                print("WARNING: Loaded variable '%s' which was not previously present in the config." % key)  # NOQA E501
            setattr(self, key, value)

        self.update_num_iterations()
