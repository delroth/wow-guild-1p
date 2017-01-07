import React, { Component } from 'react';
import DataVis from './DataVis';
import GuildPicker from './GuildPicker';
import './App.css';

class App extends Component {
  constructor(props) {
    super(props);

    this.state = {
      config: null,
      data: null,
      data_path: props.fragment,
    };
  }

  componentDidMount() {
    fetch("config.json").then((response) => {
      if (response.ok) {
        response.json().then((json) => {
          this.setState({config: json});
        });
      }
    });

    if (this.state.data_path !== '') {
      this.loadData(this.state.data_path);
    }
  }

  dataPathChanged = (path) => {
    window.location.hash = path;
    this.setState({data_path: path});
    this.loadData(path);
  }

  loadData(path) {
    fetch(path).then((response) => {
      if (response.ok) {
        response.json().then((json) => {
          this.setState({data: json});
        });
      }
    });
  }

  render() {
    return (
      <div className="App">
        <div className="App-header">
          <p className="App-intro">WoW Guild one-pager</p>
        </div>
        <GuildPicker config={this.state.config} data_path={this.state.data_path}
                     onChange={this.dataPathChanged} />
        <DataVis config={this.state.config} data={this.state.data} />
      </div>
    );
  }
}

export default App;
