import React, { Component } from 'react';
import classNames from 'classnames';
import './DataVis.css';

class DataVis extends Component {
  summarizeProgress(progress) {
    var summary = [];
    this.props.config.progress_raids.forEach((raid) => {
      var raid_summary = []
      var num_bosses = 0;
      var raid_progress = progress[raid];
      ["normal", "heroic", "mythic"].forEach((difficulty) => {
        var difficulty_progress = raid_progress[difficulty];
        var downed = 0;
        if (difficulty_progress) {
          num_bosses = Math.max(num_bosses, difficulty_progress["total"]);
          downed = difficulty_progress["downed"];
        }
        var class_name = classNames(
          'DataVis-raid-' + difficulty,
          {'DataVis-raid-cleared': downed === num_bosses},
        );
        raid_summary.push(<span className={class_name}>{downed}</span>);
        raid_summary.push(" ");
      });
      raid_summary.push(" /" + num_bosses);
      summary.push(<span className="DataVis-raid-summary">{raid_summary}</span>);
    });
    return summary;
  }

  computeProgressScore(progress) {
    var score = 0;
    var base = 1;
    var raid_multiplier = 2;
    var difficulty_multiplier = 3;
    this.props.config.progress_raids.forEach((raid) => {
      var raid_base = base;
      ["normal", "heroic", "mythic"].forEach((difficulty) => {
        var difficulty_base = raid_base;
        var difficulty_progress = progress[raid][difficulty];
        if (difficulty_progress) {
          score += difficulty_base *
            (difficulty_progress.downed / difficulty_progress.total);
        }
        raid_base *= difficulty_multiplier;
      });
      base *= raid_multiplier;
    });
    return score;
  }

  render() {
    if (this.props.config === null || this.props.data === null) {
      return null;
    }

    var rows = Object.values(this.props.data.mates).map((mate) => {
      return {
        name: mate.name,
        class: mate.class,
        level: mate.level,
        ilvl: mate.ilvl,
        progress: this.summarizeProgress(mate.progress),
        progressScore: this.computeProgressScore(mate.progress),
      };
    });

    // TODO: Make sorting configurable.
    rows.sort((a, b) => b.progressScore - a.progressScore);

    rows = rows.map((row) => (
      <tr key={row.name}>
        <td>{row.name}</td>
        <td>{row.class}</td>
        <td>{row.level}</td>
        <td>{row.ilvl}</td>
        <td>{row.progress}</td>
      </tr>
    ));

    return (
      <table className="DataVis">
        <thead>
          <tr>
            <th>Name</th>
            <th>Class</th>
            <th>Level</th>
            <th>ILVL</th>
            <th>Progress</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    );
  }
}

export default DataVis;
