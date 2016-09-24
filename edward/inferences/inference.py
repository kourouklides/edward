from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import six
import tensorflow as tf

from edward.models import RandomVariable, StanModel
from edward.util import get_session, placeholder


class Inference(object):
  """Base class for Edward inference methods.

  Attributes
  ----------
  latent_vars : dict of RandomVariable to RandomVariable
    Collection of random variables to perform inference on. Each
    random variable is binded to another random variable; the latter
    will infer the former conditional on data.
  data : dict
    Data dictionary whose values may vary at each session run.
  model_wrapper : ed.Model or None
    An optional wrapper for the probability model. If specified, the
    random variables in `latent_vars`' dictionary keys are strings
    used accordingly by the wrapper.
  """
  def __init__(self, latent_vars, data=None, model_wrapper=None):
    """Initialization.

    Parameters
    ----------
    latent_vars : dict of RandomVariable to RandomVariable
      Collection of random variables to perform inference on. Each
      random variable is binded to another random variable; the latter
      will infer the former conditional on data.
    data : dict, optional
      Data dictionary which binds observed variables (of type
      `RandomVariable`) to their realizations (of type `tf.Tensor`).
      It can also bind placeholders (of type `tf.Tensor`) used in the
      model to their realizations.
    model_wrapper : ed.Model, optional
      A wrapper for the probability model. If specified, the random
      variables in `latent_vars`' dictionary keys are strings
      used accordingly by the wrapper. `data` is also changed. For
      TensorFlow, Python, and Stan models, the key type is a string;
      for PyMC3, the key type is a Theano shared variable. For
      TensorFlow, Python, and PyMC3 models, the value type is a NumPy
      array or TensorFlow tensor; for Stan, the value type is the
      type according to the Stan program's data block.

    Notes
    -----
    If ``data`` is not passed in, the dictionary is empty.

    Three options are available for batch training:
    1. internally if user passes in data as a dictionary of NumPy
       arrays;
    2. externally if user passes in data as a dictionary of
       TensorFlow placeholders (and manually feeds them);
    3. externally if user passes in data as TensorFlow tensors
       which are the outputs of data readers.

    Examples
    --------
    >>> mu = Normal(mu=tf.constant([0.0]), sigma=tf.constant([1.0]))
    >>> x = Normal(mu=tf.ones(N) * mu, sigma=tf.constant([1.0]))
    >>>
    >>> qmu_mu = tf.Variable(tf.random_normal([1]))
    >>> qmu_sigma = tf.nn.softplus(tf.Variable(tf.random_normal([1])))
    >>> qmu = Normal(mu=qmu_mu, sigma=qmu_sigma)
    >>>
    >>> Inference({mu: qmu}, {x: np.array()})
    """
    sess = get_session()
    if not isinstance(latent_vars, dict):
      raise TypeError()

    if data is None:
      data = {}
    elif not isinstance(data, dict):
      raise TypeError()

    self.latent_vars = latent_vars
    self.model_wrapper = model_wrapper

    if isinstance(model_wrapper, StanModel):
      # Stan models do no support data subsampling because they
      # take arbitrary data structure types in the data block
      # and not just NumPy arrays (this makes it unamenable to
      # TensorFlow placeholders). Therefore fix the data
      # dictionary ``self.data`` at compile time to ``data``.
      self.data = data
    else:
      self.data = {}
      for key, value in six.iteritems(data):
        if isinstance(key, RandomVariable) or isinstance(key, str):
          if isinstance(value, tf.Tensor):
            # If ``data`` has TensorFlow placeholders, the user
            # must manually feed them at each step of
            # inference.
            # If ``data`` has tensors that are the output of
            # data readers, then batch training operates
            # according to the reader.
            self.data[key] = tf.cast(value, tf.float32)
          elif isinstance(value, np.ndarray):
            # If ``data`` has NumPy arrays, store the data
            # in the computational graph.
            ph = placeholder(tf.float32, value.shape)
            var = tf.Variable(ph, trainable=False, collections=[])
            self.data[key] = var
            sess.run(var.initializer, {ph: value})
          else:
            raise NotImplementedError()
        else:
          # If key is a placeholder, then don't modify its fed value.
          self.data[key] = value

  def run(self, *args, **kwargs):
    """A simple wrapper to run inference.

    1. Initialize via ``initialize``.
    2. Run ``update`` for ``self.n_iter`` iterations.
    3. While running, ``print_progress``.
    4. Finalize via ``finalize``.

    Parameters
    ----------
    *args
      Passed into ``initialize``.
    **kwargs
      Passed into ``initialize``.
    """
    self.initialize(*args, **kwargs)
    for t in range(self.n_iter + 1):
      info_dict = self.update()
      self.print_progress(t, info_dict)

    self.finalize()

  def initialize(self, n_iter=1000, n_print=100, logdir=None):
    """Initialize inference algorithm.

    Parameters
    ----------
    n_iter : int, optional
      Number of iterations for algorithm.
    n_print : int, optional
      Number of iterations for each print progress. To suppress print
      progress, then specify None.
    logdir : str, optional
      Directory where event file will be written. For details,
      see `tf.train.SummaryWriter`. Default is to write nothing.
    """
    self.n_iter = n_iter
    self.n_print = n_print

    if logdir is not None:
      train_writer = tf.train.SummaryWriter(logdir, tf.get_default_graph())

  def update(self):
    """Run one iteration of inference.

    Returns
    -------
    dict
      Dictionary of algorithm-specific information.
    """
    return {}

  def print_progress(self, t, info_dict):
    """Print progress to output.

    Parameters
    ----------
    t : int
      Iteration counter.
    info_dict : dict
      Dictionary of algorithm-specific information.
    """
    pass

  def finalize(self):
    """Function to call after convergence.
    """
    pass
