import unittest
import log_analyzer
import os


class SimplisticTest(unittest.TestCase):

    def test(self):
        conf = {'LOG_DIR': './test/log', 'REPORT_DIR': './test/report', 'FORCE': True, 'REPORT_SIZE': 100}
        f = open(os.path.join(conf['REPORT_DIR'], 'report_target.html'), 'r', encoding='utf-8')
        target = f.read()
        f.close()
        target_file = os.path.join(conf['REPORT_DIR'], 'report-2018.06.30.html')
        if os.path.isfile(target_file):
            os.remove(target_file)
        log_analyzer.main(conf)
        try:
            f = open(target_file, 'r', encoding='utf-8')
            result = f.read()
            f.close()
        except:
            result = ''
        self.assertTrue(target == result)

if __name__ == '__main__':
    unittest.main()
