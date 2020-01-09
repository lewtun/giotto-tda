"""Static and interactive visualisation functions for Mapper graphs."""
# License: GNU AGPLv3

import logging
import operator
import traceback
from functools import reduce

import numpy as np
import plotly.graph_objects as go
from IPython.display import display
from ipywidgets import Layout, widgets
from matplotlib.cm import get_cmap
from matplotlib.colors import rgb2hex
from sklearn.base import clone

from .utils._logging import OutputWidgetHandler
from .utils.visualization import (_get_column_color_buttons, _get_node_colors,
                                  _get_node_size, _get_node_text,
                                  _infer_color_variable_kind, set_node_sizeref)


def create_static_network(pipeline, data, layout='kamada_kawai', layout_dim=2,
                          color_variable=None, node_color_statistic=np.mean,
                          color_by_columns_dropdown=False, plotly_kwargs=None,
                          clone_pipeline=True):
    """
    Parameters
    ----------
    pipeline : :class:`MapperPipeline` object
        Mapper pipeline to act on to data.

    data : array-like of shape (n_samples, n_features)
        Data used to generate the Mapper graph. Can be a pandas dataframe.

    layout : None, str or callable, optional, default: ``'kamada-kawai'``
        Layout algorithm for the graph. Can be any accepted value for the
        ``layout`` parameter in the :meth:`layout` method of
        :class:`igraph.Graph`. [1]_

    layout_dim : int, default: ``2``
        The number of dimensions for the layout. Can be 2 or 3.

    color_variable : object or None, optional, default: ``None``
        Specifies which quantity is to be used for node coloring.

            1. If a numpy ndarray or pandas dataframe, :attr:`color_variable`
               must have the same length as :attr:`data` and is interpreted as
               a quantity of interest according to which node of the Mapper
               graph is to be colored (see :attr:`node_color_statistic`).
            2. If ``None`` then equivalent to passing :attr:`data`.
            3. If an object implementing :meth:`transform` or
               :meth:`fit_transform`, e.g. a scikit-learn estimator or
               pipeline, it is applied to :attr:`data` to generate the quantity
               of interest.
            4. If an index or string, or list of indices / strings, equivalent
               to selecting a column or subset of columns from :attr:`data`.

    node_color_statistic : callable, or ndarray of shape (n_nodes,) or \
        (n_nodes, 1), optional, default: ``numpy.mean``
        Specifies how to determine the colors of each node. If a
        numpy array, it must have the same length as the number of nodes in
        the Mapper graph, and its values are used directly for node
        coloring, ignoring :attr:`color_variable`. Otherwise, it must be a
        callable object and is used to obtain a summary statistic within
        each Mapper node of the quantity specified by :attr:`color_variable`.

    color_by_columns_dropdown : bool, optional, default: ``True``
        If ``True``, a dropdown widget is generated which allows the user to
        color Mapper nodes according to any column in `data`.

    plotly_kwargs : dict, optional, default: ``None``
        Keyword arguments to configure the Plotly Figure.

    clone_pipeline : bool, default: ``True``
        If ``True``, the input :class:`pipeline` is cloned before computing the
        Mapper graph to prevent unexepected side effects from in-place
        parameter updates.

    Returns
    -------
    fig : ploty.graph_objs.Figure
        The figure representing the nerve (topological graph).

    References
    ----------
    .. [1] `igraph.Graph.layout
            <https://igraph.org/python/doc/igraph.Graph-class.html#layout>`_.

    """

    # Compute the graph and fetch the indices of points in each node
    if clone_pipeline:
        pipe = clone(pipeline)
    else:
        pipe = pipeline
    graph = pipe.fit_transform(data)
    node_elements = graph['node_metadata']['node_elements']

    # Simple duck typing to determine whether data is a pandas dataframe
    is_data_dataframe = hasattr(data, 'columns')

    # Determine whether layout is an array of node positions
    is_layout_ndarray = hasattr(layout, 'dtype')
    if is_layout_ndarray:
        node_pos = layout
    else:
        node_pos = graph.layout(layout, dim=layout_dim)

    color_variable_kind = _infer_color_variable_kind(color_variable, data)

    # Determine whether node_colors is an array of node colors
    is_node_colors_ndarray = hasattr(node_color_statistic, 'dtype')
    if (not is_node_colors_ndarray) and (not callable(node_color_statistic)):
        raise ValueError("node_color_statistic must be a callable or ndarray.")

    _node_colors = _get_node_colors(
        data, is_data_dataframe, node_elements,
        is_node_colors_ndarray, node_color_statistic,
        color_variable, color_variable_kind)

    plot_options = {
        'edge_trace_mode': 'lines',
        'edge_trace_line': dict(color='#888', width=1),
        'edge_trace_hoverinfo': 'none',
        'node_trace_mode': 'markers',
        'node_trace_hoverinfo': 'text',
        'node_trace_hoverlabel': dict(
            bgcolor=list(map(lambda x: rgb2hex(get_cmap('viridis')(x)),
                             _node_colors))),
        'node_trace_marker_color': list(
            map(lambda x: rgb2hex(get_cmap('viridis')(x)), _node_colors)),
        'node_trace_marker_colorscale': 'viridis',
        'node_trace_marker_showscale': True,
        'node_trace_marker_reversescale': False,
        'node_trace_marker_line': dict(width=.5, color='#888'),
        'node_trace_marker_size': _get_node_size(node_elements),
        'node_trace_marker_sizemode': 'area',
        'node_trace_marker_sizeref': set_node_sizeref(node_elements),
        'node_trace_marker_sizemin': 4,
        'node_trace_marker_cmin': np.min(_node_colors),
        'node_trace_marker_cmax': np.max(_node_colors),
        'node_trace_marker_colorbar': dict(thickness=15,
                                           title='',
                                           xanchor='left',
                                           titleside='right'),
        'node_trace_marker_line_width': 2,
        'node_trace_text': _get_node_text(graph),
        'layout_showlegend': False,
        'layout_hovermode': 'closest',
        'layout_xaxis_title': "",
        'layout_yaxis_title': "",
        'layout_title': "",
        'layout_margin': {'b': 20, 'l': 5, 'r': 5, 't': 40},
        'layout_annotations': list()
    }

    if plotly_kwargs is not None:
        plot_options.update(plotly_kwargs)

    # Define layout options that are common to 2D and 3D figures
    layout_options_common = go.Layout(
        showlegend=plot_options['layout_showlegend'],
        hovermode=plot_options['layout_hovermode'],
        margin=plot_options['layout_margin'],
        autosize=False
    )

    # TODO check we are not losing performance by using map + lambda
    edge_x = list(reduce(operator.iconcat,
                         map(lambda x: [node_pos[x[0]][0],
                                        node_pos[x[1]][0], None],
                             graph.get_edgelist()), []))
    edge_y = list(reduce(operator.iconcat,
                         map(lambda x: [node_pos[x[0]][1],
                                        node_pos[x[1]][1], None],
                             graph.get_edgelist()), []))

    node_x = [node_pos[k][0] for k in range(graph.vcount())]
    node_y = [node_pos[k][1] for k in range(graph.vcount())]

    if layout_dim == 2:
        plot_options.update({
            'layout_xaxis': dict(showgrid=False, zeroline=False,
                                 showticklabels=False, ticks="",
                                 showline=False),
            'layout_yaxis': dict(showgrid=False, zeroline=False,
                                 showticklabels=False, ticks="",
                                 showline=False),
        })
        edge_trace = go.Scatter(
            x=edge_x,
            y=edge_y,
            line=plot_options['edge_trace_line'],
            hoverinfo=plot_options['edge_trace_hoverinfo'],
            mode=plot_options['edge_trace_mode'])

        node_trace = go.Scatter(
            x=node_x,
            y=node_y,
            mode=plot_options['node_trace_mode'],
            hoverinfo=plot_options['node_trace_hoverinfo'],
            hovertext=plot_options['node_trace_text'],
            marker=dict(
                showscale=plot_options['node_trace_marker_showscale'],
                colorscale=plot_options['node_trace_marker_colorscale'],
                reversescale=plot_options['node_trace_marker_reversescale'],
                line=plot_options['node_trace_marker_line'],
                color=list(
                    map(lambda x: rgb2hex(
                        get_cmap(
                            plot_options['node_trace_marker_colorscale']
                        )(x)), _node_colors)),
                size=plot_options['node_trace_marker_size'],
                sizemode=plot_options['node_trace_marker_sizemode'],
                sizeref=plot_options['node_trace_marker_sizeref'],
                sizemin=plot_options['node_trace_marker_sizemin'],
                cmin=plot_options['node_trace_marker_cmin'],
                cmax=plot_options['node_trace_marker_cmax'],
                colorbar=plot_options['node_trace_marker_colorbar'],
                line_width=plot_options['node_trace_marker_line_width']),
            text=plot_options['node_trace_text'])

        layout_options_2d = {
            'layout_xaxis': plot_options['layout_xaxis'],
            'layout_xaxis_title': plot_options['layout_xaxis_title'],
            'layout_yaxis': plot_options['layout_yaxis'],
            'layout_yaxis_title': plot_options['layout_yaxis_title'],
            'layout_template': 'simple_white',
        }
        fig = go.FigureWidget(data=[edge_trace, node_trace],
                              layout=layout_options_common)
        fig.update(layout_options_2d)

    elif layout_dim == 3:
        plot_options.update({
            'axis': dict(showbackground=False,
                         showline=False,
                         zeroline=False,
                         showgrid=False,
                         showticklabels=False,
                         title='')
        })
        plot_options['layout_scene'] = dict(xaxis=dict(plot_options['axis']),
                                            yaxis=dict(plot_options['axis']),
                                            zaxis=dict(plot_options['axis'])
                                            )

        edge_z = list(reduce(operator.iconcat,
                             map(lambda x: [node_pos[x[0]][2],
                                            node_pos[x[1]][2], None],
                                 graph.get_edgelist()), []))

        node_z = [node_pos[k][2] for k in range(graph.vcount())]

        edge_trace = go.Scatter3d(
            x=edge_x,
            y=edge_y,
            z=edge_z,
            mode=plot_options['edge_trace_mode'],
            line=plot_options['edge_trace_line'],
            hoverinfo=plot_options['edge_trace_hoverinfo'])

        node_trace = go.Scatter3d(
            x=node_x,
            y=node_y,
            z=node_z,
            mode=plot_options['node_trace_mode'],
            hoverinfo=plot_options['node_trace_hoverinfo'],
            hoverlabel=plot_options['node_trace_hoverlabel'],
            marker=dict(
                showscale=plot_options['node_trace_marker_showscale'],
                colorscale=plot_options['node_trace_marker_colorscale'],
                reversescale=plot_options['node_trace_marker_reversescale'],
                line=plot_options['node_trace_marker_line'],
                color=plot_options['node_trace_marker_color'],
                size=plot_options['node_trace_marker_size'],
                sizemode=plot_options['node_trace_marker_sizemode'],
                sizeref=plot_options['node_trace_marker_sizeref'],
                sizemin=plot_options['node_trace_marker_sizemin'],
                cmin=plot_options['node_trace_marker_cmin'],
                cmax=plot_options['node_trace_marker_cmax'],
                colorbar=plot_options['node_trace_marker_colorbar'],
                line_width=plot_options['node_trace_marker_line_width']),
            text=plot_options['node_trace_text'])

        layout_options_3d = {
            'layout_scene': plot_options['layout_scene'],
            'layout_annotations': plot_options['layout_annotations'],
        }

        fig = go.FigureWidget(data=[edge_trace, node_trace],
                              layout=layout_options_common)
        fig.update(layout_options_3d)

    # Compute node colors according to data columns only if necessary
    if color_by_columns_dropdown:
        column_color_buttons = _get_column_color_buttons(
            data, is_data_dataframe, node_elements, _node_colors,
            plot_options['node_trace_marker_colorscale'])
    else:
        column_color_buttons = None

    button_height = 1.1
    fig.update_layout(
        updatemenus=[
            go.layout.Updatemenu(
                buttons=column_color_buttons,
                direction="down",
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.11,
                xanchor='left',
                y=button_height,
                yanchor="top"
            ),
        ])

    if color_by_columns_dropdown:
        fig.add_annotation(
            go.layout.Annotation(text="Color by:", x=0, xref="paper",
                                 y=button_height - 0.045,
                                 yref="paper", align="left", showarrow=False)
        )

    return fig


def create_interactive_network(pipeline, data, layout='kamada_kawai',
                               layout_dim=2, color_variable=None,
                               node_color_statistic=np.mean,
                               color_by_columns_dropdown=False,
                               plotly_kwargs=None):
    """
    Parameters
    ----------
    pipeline : :class:`MapperPipeline` object
        Mapper pipeline to act on to data.

    data : array-like of shape (n_samples, n_features)
        Data used to generate the Mapper graph. Can be a pandas dataframe.

    layout : None, str or callable, optional, default: ``'kamada-kawai'``
        Layout algorithm for the graph. Can be any accepted value for the
        ``layout`` parameter in the :meth:`layout` method of
        :class:`igraph.Graph`. [1]_

    layout_dim : int, default: ``2``
        The number of dimensions for the layout. Can be 2 or 3.

    color_variable : object or None, optional, default: ``None``
        Specifies which quantity is to be used for node coloring.

            1. If a numpy ndarray or pandas dataframe, :attr:`color_variable`
               must have the same length as :attr:`data` and is interpreted as
               a quantity of interest according to which node of the Mapper
               graph is to be colored (see :attr:`node_color_statistic`).
            2. If ``None`` then equivalent to passing :attr:`data`.
            3. If an object implementing :meth:`transform` or
               :meth:`fit_transform`, e.g. a scikit-learn estimator or
               pipeline, it is applied to :attr:`data` to generate the quantity
               of interest.
            4. If an index or string, or list of indices / strings, equivalent
               to selecting a column or subset of columns from :attr:`data`.

    node_color_statistic : callable, or ndarray of shape (n_nodes,) or \
        (n_nodes, 1), optional, default: ``numpy.mean``
        Specifies how to determine the colors of each node. If a
        numpy array, it must have the same length as the number of nodes in
        the Mapper graph, and its values are used directly for node
        coloring, ignoring :attr:`color_variable`. Otherwise, it must be a
        callable object and is used to obtain a summary statistic within
        each Mapper node of the quantity specified by :attr:`color_variable`.

    color_by_columns_dropdown : bool, optional, default: ``False``
        If ``True``, a dropdown widget is generated which allows the user to
        color Mapper nodes according to any column in `data`.

    plotly_kwargs : dict, optional, default: ``None``
        Keyword arguments to configure the Plotly Figure.

    """
    pipe = clone(pipeline)

    def get_widgets_per_param(param, value):
        if isinstance(value, float):
            return (param, widgets.FloatText(
                value=value,
                step=0.05,
                description=param.split('__')[1],
                continuous_update=False,
                disabled=False
            ))
        elif isinstance(value, int):
            return (param, widgets.IntText(
                value=value,
                step=1,
                description=param.split('__')[1],
                continuous_update=False,
                disabled=False
            ))
        elif isinstance(value, str):
            return (param, widgets.Text(
                value=value,
                description=param.split('__')[1],
                continuous_update=False,
                disabled=False
            ))
        else:
            return None

    def update_figure(old_figure, new_figure, dim):
        # TODO could this be abstracted to node and edge traces and metadata
        # information without need for creating a full new figure object
        old_figure.data[0].x = new_figure.data[0].x
        old_figure.data[0].y = new_figure.data[0].y
        old_figure.data[1].x = new_figure.data[1].x
        old_figure.data[1].y = new_figure.data[1].y

        if dim == 3:
            old_figure.data[0].z = new_figure.data[0].z
            old_figure.data[1].z = new_figure.data[1].z

        old_figure.data[1].marker.size = new_figure.data[1].marker.size
        old_figure.data[1].marker.color = new_figure.data[1].marker.color
        old_figure.data[1].marker.sizeref = new_figure.data[1].marker.sizeref

    def on_parameter_change(change):
        handler.clear_logs()
        try:
            for param, value in cover_params.items():
                if isinstance(value, (int, float, str)):
                    pipe.set_mapper_params(
                        **{param: cover_params_widgets[param].value})
            for param, value in cluster_params.items():
                if isinstance(value, (int, float, str)):
                    pipe.set_mapper_params(
                        **{param: cluster_params_widgets[param].value})

            new_fig = create_static_network(
                pipe, data, layout, layout_dim, color_variable,
                node_color_statistic, color_by_columns_dropdown, plotly_kwargs,
                clone_pipeline=False)

            logger.info("Updating figure ...")
            with fig.batch_update():
                update_figure(fig, new_fig, layout_dim)
            valid.value = True
        except Exception:
            exception_data = traceback.format_exc().splitlines()
            logger.exception(exception_data[-1])
            valid.value = False

    def observe_widgets(params, widgets):
        for param, value in params.items():
            if isinstance(value, (int, float, str)):
                widgets[param].observe(on_parameter_change, names='value')

    # define output widget to capture logs
    out = widgets.Output()

    @out.capture()
    def click_box(change):
        if logs_box.value:
            out.clear_output()
            handler.show_logs()
        else:
            out.clear_output()

    # initialise logging
    logger = logging.getLogger(__name__)
    handler = OutputWidgetHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s  - [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # initialise cover and cluster dictionaries of parameters and widgets
    cover_params = dict(filter(lambda x: x[0].startswith('cover'),
                               pipe.get_mapper_params().items()))
    cover_params_widgets = dict(
        filter(None, map(lambda x: get_widgets_per_param(*x),
                         cover_params.items())))
    cluster_params = dict(filter(lambda x: x[0].startswith('clusterer'),
                                 pipe.get_mapper_params().items()))
    cluster_params_widgets = dict(
        filter(None, map(lambda x: get_widgets_per_param(*x),
                         cluster_params.items())))

    # initialise widgets for validating input parameters of pipeline
    valid = widgets.Valid(
        value=True,
        description='Valid parameters',
        style={'description_width': '100px'},
    )

    # initialise widget for showing the logs
    logs_box = widgets.Checkbox(
        description='Show logs: ',
        value=False,
        indent=False
    )

    # initialise figure with initial pipeline and config
    if plotly_kwargs is None:
        plotly_kwargs = dict()

    fig = create_static_network(
        pipe, data, layout, layout_dim, color_variable, node_color_statistic,
        color_by_columns_dropdown, plotly_kwargs, clone_pipeline=False)

    observe_widgets(cover_params, cover_params_widgets)
    observe_widgets(cluster_params, cluster_params_widgets)

    logs_box.observe(click_box, names='value')

    # define containers for input widgets
    container_cover = widgets.HBox(
        children=list(cover_params_widgets.values()))

    container_cluster_layout = Layout(display='flex', flex_flow='row wrap')

    container_cluster = widgets.HBox(
        children=list(cluster_params_widgets.values()),
        layout=container_cluster_layout)

    box = widgets.VBox(
        [container_cover, container_cluster, fig, valid, logs_box])
    display(box, out)
