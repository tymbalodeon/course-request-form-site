function addAdditionalEnrollmentRow() {
  const next_enrollment_input_id =
    document.getElementById("additional_enrollments").childElementCount + 1;
  const node = document.createElement("DIV");
  node.setAttribute("id", `addEnroll-${next_enrollment_input_id}`);
  node.setAttribute("class", "additional-enrollments");
  const id = `'additional_enrollments','addEnroll-${next_enrollment_input_id}'`;
  const user = `'additional_enrollments[${next_enrollment_input_id}][user]'`;
  const role = `'additional_enrollments[${next_enrollment_input_id}][role]'`;
  node.insertAdjacentHTML(
    "beforeend",
    `<label class="additional-enrollments-user">
         User (pennkey)
         <input name="${user}" value="" class="form-control" type="text">
     </label>
     <label class="additional-enrollments-role">
          Role
          <select id="choose" name="${role}">
              <option disabled selected>Please select</option>
              <option value="TA">TA</option>
              <option value="DES">Designer</option>
              <option value="LIB">Librarian</option>
          </select>
      </label>
      <a class="additional-enrollments-delete" onClick="removeAdditionalEnrollmentRow(${id})">
          Delete
          <i class="fas fa-times"></i>
      </a>`
  );
  document.getElementById("additional_enrollments").appendChild(node);
}

function removeAdditionalEnrollmentRow(parentDiv, childDiv) {
  console.log("HELLOW");
  if (childDiv == parentDiv) {
    alert("Cannot remove parent div.");
  } else if (document.getElementById(childDiv)) {
    const child = document.getElementById(childDiv);
    const parent = document.getElementById(parentDiv);
    parent.removeChild(child);
  } else {
    alert("Child div has already been removed or does not exist.");
    return false;
  }
}
