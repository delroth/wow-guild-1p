import React, { Component } from 'react';

class GuildPicker extends Component {
  guildSelected = (e) => {
    this.props.onChange(e.target.value);
  }

  render() {
    if (this.props.config === null) {
      return <p>Loading configuration...</p>;
    }

    var guilds = this.props.config.guilds.map((guild) => {
      return {
        path: guild.path,
        descr: guild.region + " - " + guild.realm + " - " + guild.name,
      }
    });
    guilds.sort((a, b) => a.descr.localeCompare(b.descr));

    guilds = guilds.map((guild) => {
      return (
        <option key={guild.path} value={guild.path}>
          {guild.descr}
        </option>
      );
    });

    return (
      <select defaultValue={this.props.data_path} onChange={this.guildSelected}>
        <option value="" disabled>Select guild.</option>
        {guilds}
      </select>
    );
  }
}

export default GuildPicker;
