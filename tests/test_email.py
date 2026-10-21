"""Compact-package integrity, geometry and deterministic reproduction."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from airspace.analysis import load_inputs,load_rules
from airspace.vertical import VerticalTrajectory,VerticalSegment
from tools.build_email import FILES,build,package,plotting_profile,validate_github_url


class EmailTests(unittest.TestCase):
    def test_six_flat_files_complete_evidence_and_unchanged_controls(self):
        directory=ROOT/'email_delivery'
        self.assertEqual(set(p.name for p in directory.iterdir()),set(FILES))
        evidence=json.loads((directory/'verification.json').read_text())
        original=json.loads((ROOT/'submission/evidence.json').read_text())
        self.assertEqual(evidence['certificate'],original['verification'])
        self.assertEqual(evidence['quality'],original['quality'])
        self.assertEqual(evidence['github_url'],'https://github.com/Timur713/DTL')
        for name,expected in evidence['file_sha256'].items():
            self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),expected,name)
        for name in ('trajectories.csv','segments.json','rules.json'):
            self.assertEqual((directory/name).read_bytes(),(ROOT/'submission'/name).read_bytes())
        self.assertLess(len((directory/'README.md').read_text().split()),500)

    def test_archive_has_no_navigation_tree_and_matches_files(self):
        with zipfile.ZipFile(ROOT/'DTL_email.zip') as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(),list(FILES))
            self.assertLess((ROOT/'DTL_email.zip').stat().st_size,1500000)
            for name in FILES:self.assertEqual(archive.read(name),(ROOT/'email_delivery'/name).read_bytes())

    def test_plotting_band_known_sphere_geometry_and_cpa(self):
        scenario,_=load_inputs(ROOT/'scenario.json');rules=load_rules(ROOT/'rules.json')
        scenario['hostile_object'].update(x_m=0,y_m=0,alt_m=0,vx_mps=0,vy_mps=0,vz_mps=0)
        scenario['target'].update(x_m=1e6,y_m=1e6)
        flight=dict(flight_id='A',x_m=-6000,y_m=0,alt_m=3000,vx_mps=200,vy_mps=0,vz_mps=0)
        definition=VerticalTrajectory(flight,[VerticalSegment(1200,0)],scenario,rules).to_dict()
        profile=plotting_profile(definition,flight,scenario,rules)['profile']
        index=profile['time_s'].index(30)
        self.assertEqual(profile['threat_band_m'][index],[-5000,5000])
        self.assertEqual(profile['alt_m'][index],3000)
        self.assertIsNone(profile['threat_band_m'][profile['time_s'].index(0)])
        self.assertTrue(all(b is None for b in profile['target_band_m']))
        self.assertIn(1200,profile['time_s'])

    def test_github_url_and_output_protection(self):
        self.assertIsNone(validate_github_url(None))
        self.assertEqual(validate_github_url('https://github.com/Timur713/DTL/'),'https://github.com/Timur713/DTL')
        for value in ('javascript:alert(1)','http://github.com/Timur713/DTL','https://example.com/Timur713/DTL','https://github.com/Timur713/DTL?test=1'):
            with self.assertRaises(ValueError):validate_github_url(value)
        with self.assertRaises(ValueError):build(ROOT/'submission')
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'unrelated';p.mkdir();(p/'keep.txt').write_text('keep')
            with self.assertRaises(ValueError):build(p)
            self.assertEqual((p/'keep.txt').read_text(),'keep')

    def test_export_and_archive_reproduce_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as t:
            directory=Path(t)/'compact'
            build(directory,'https://github.com/Timur713/DTL')
            for name in FILES:self.assertEqual((directory/name).read_bytes(),(ROOT/'email_delivery'/name).read_bytes(),name)
            target=Path(t)/'compact.zip';package(directory,target)
            self.assertEqual(target.read_bytes(),(ROOT/'DTL_email.zip').read_bytes())


if __name__=='__main__':unittest.main()
