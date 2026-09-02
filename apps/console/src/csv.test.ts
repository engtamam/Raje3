import { describe, expect, it } from 'vitest';
import { parseCsv, csvToObjects } from './csv';

describe('parseCsv', () => {
  it('parses plain comma-separated rows', () => {
    expect(parseCsv('a,b,c\n1,2,3')).toEqual([['a', 'b', 'c'], ['1', '2', '3']]);
  });

  it('a quoted field may hold a comma', () => {
    expect(parseCsv('name,note\n"قص شعر, رجالي",ok')).toEqual([
      ['name', 'note'], ['قص شعر, رجالي', 'ok'],
    ]);
  });

  it('an escaped double-quote inside a quoted field', () => {
    expect(parseCsv('name\n"يقول ""مرحباً"""')).toEqual([['name'], ['يقول "مرحباً"']]);
  });

  it('CRLF and LF line endings both work', () => {
    expect(parseCsv('a,b\r\n1,2\r\n')).toEqual([['a', 'b'], ['1', '2']]);
    expect(parseCsv('a,b\n1,2\n')).toEqual([['a', 'b'], ['1', '2']]);
  });

  it('a blank line is dropped, not read as a one-column row', () => {
    expect(parseCsv('a,b\n1,2\n\n3,4')).toEqual([['a', 'b'], ['1', '2'], ['3', '4']]);
  });
});

describe('csvToObjects', () => {
  it('keys objects by the header row, trimmed and lower-cased', () => {
    expect(csvToObjects([[' Name ', 'Price'], ['قص شعر', '50']])).toEqual([
      { name: 'قص شعر', price: '50' },
    ]);
  });

  it('a short row pads missing cells with empty string, not undefined', () => {
    expect(csvToObjects([['name', 'price'], ['قص شعر']])).toEqual([{ name: 'قص شعر', price: '' }]);
  });

  it('empty input is an empty list, not a crash on rows[0]', () => {
    expect(csvToObjects([])).toEqual([]);
  });
});
