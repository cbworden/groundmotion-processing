#!/usr/bin/env python
import io
import os
import shutil
import pkg_resources

from gmprocess.utils import constants


def test_compute_waveform_metrics(script_runner):
    try:
        # Need to create profile first.
        cdir = constants.PROJECTS_PATH_TEST
        ddir = pkg_resources.resource_filename(
            'gmprocess', os.path.join('data', 'testdata',
                                      'demo_steps', 'compute_metrics'))

        # Make a copy of the hdf files
        events = ['ci38038071', 'ci38457511']
        for event in events:
            src = os.path.join(ddir, event, 'workspace.h5')
            dst = os.path.join(ddir, event, '_workspace.h5')
            shutil.copyfile(src, dst)

        setup_inputs = io.StringIO(
            "test\n%s\n%s\nname\nemail\n" % (cdir, ddir)
        )
        ret = script_runner.run('gmp', 'projects', '-c', stdin=setup_inputs)
        setup_inputs.close()
        assert ret.success

        ret = script_runner.run('gmp', 'compute_waveform_metrics')
        assert ret.success

        assert "Added waveform metrics to workspace files with" in ret.stderr
        assert "Calculating waveform metrics for CE.23837.HN" in ret.stderr
        assert "Calculating waveform metrics for CI.TOW2.HN" in ret.stderr
    except Exception as ex:
        raise ex
    finally:
        shutil.rmtree(constants.PROJECTS_PATH_TEST)
        # Move the hdf files back
        events = ['ci38038071', 'ci38457511']
        for event in events:
            dst = os.path.join(ddir, event, 'workspace.h5')
            src = os.path.join(ddir, event, '_workspace.h5')
            shutil.move(src, dst)


if __name__ == '__main__':
    test_compute_waveform_metrics()
