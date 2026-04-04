import React from 'react'
import { Link } from "react-router-dom";

let getTitle = (note) => {
    let title = note.body.split('\n')[0].trim()
    if (!title) {
        title = 'Untitled note'
    }
    if (title.length > 25) {
        title = title.slice(0, 25) + '...'
    }
    return title
}
let getDate = (note) => {
    return new Date(note.updated).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
    })
}
let getContent = (note) => {
    let title = note.body.split('\n')[0]
    let content = note.body.replace(title, "").trim()
    if (!content) {
        return 'Open this note to start writing more details.'
    }
    if (content.length > 69) {
        return content.slice(0, 69) + '...'
    }
    return content
}

const ListItem = ({note}) => {
    return (
    <Link className='notes-list-item' to={`/note/${note.id}`}>
        <div className='notes-list-item-top'>
            <p className='notes-list-item-label'>Note</p>
            <p className='notes-list-item-date'>{getDate(note)}</p>
        </div>
        <h3>{getTitle(note)}</h3>
        <p className='notes-list-item-body'>{getContent(note)}</p>
    </Link>
  )
}

export default ListItem
