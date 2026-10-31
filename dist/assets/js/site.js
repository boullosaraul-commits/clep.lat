document.addEventListener("DOMContentLoaded",()=>{
  const button=document.querySelector(".menu"),nav=document.querySelector(".links");
  if(button&&nav){
    const close=()=>{nav.classList.remove("open");button.setAttribute("aria-expanded","false");button.setAttribute("aria-label","Abrir menú")};
    button.addEventListener("click",()=>{const open=nav.classList.toggle("open");button.setAttribute("aria-expanded",String(open));button.setAttribute("aria-label",open?"Cerrar menú":"Abrir menú")});
    nav.addEventListener("click",event=>{if(event.target.closest("a"))close()});
    document.addEventListener("keydown",event=>{if(event.key==="Escape"&&nav.classList.contains("open")){close();button.focus()}});
    window.matchMedia("(max-width:1100px)").addEventListener("change",close);
  }
  document.querySelectorAll("[data-year]").forEach(element=>element.textContent=new Date().getFullYear());
});
